"""The chat rules, used by the REST endpoints and the WebSocket alike (ADR-0014).

Everything here is synchronous and takes a session; the WebSocket handler runs it in the thread
pool. Messages and names never reach a log.
"""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, Select, and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chat import push
from app.chat.listener import notify
from app.core.config import Settings
from app.core.errors import ApiError
from app.models.chat import MAX_MESSAGE_CHARS, Conversation, ConversationState, Message
from app.models.church import Person
from app.schemas.chat import ConversationOut, MessageOut, OtherPerson
from app.services.locks import lock_people
from app.services.providers import visible_provider

PREVIEW_CHARS = 60
# Control characters other than a new line and a tab are never part of a message.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def now() -> datetime:
    return datetime.now(UTC)


def side_of(conversation: Conversation, person_id: uuid.UUID) -> str | None:
    if person_id == conversation.starter_id:
        return "starter"
    if person_id == conversation.provider_id:
        return "provider"
    return None


def other_side(side: str) -> str:
    return "provider" if side == "starter" else "starter"


def other_id(conversation: Conversation, side: str) -> uuid.UUID:
    return conversation.provider_id if side == "starter" else conversation.starter_id


def open_conversation(
    db: Session, conversation_id: uuid.UUID, person: Person
) -> tuple[Conversation, str]:
    """The conversation and the person's side, or `404` for anyone who is not a participant (and
    for one that does not exist), so nothing says whether a conversation exists."""
    conversation = db.get(Conversation, conversation_id)
    side = side_of(conversation, person.id) if conversation is not None else None
    if conversation is None or side is None:
        raise ApiError(404, "not_found", "Conversation not found")
    return conversation, side


def _state(db: Session, conversation_id: uuid.UUID, side: str) -> ConversationState:
    row = db.get(ConversationState, (conversation_id, side))
    if row is None:  # created together with the conversation; this is only a safety net
        row = ConversationState(conversation_id=conversation_id, side=side)
        db.add(row)
        db.flush()
    return row


def _is_open(person: Person | None) -> bool:
    return person is not None and person.closed_at is None and person.status != "revoked"


def _between(db: Session, a: uuid.UUID, b: uuid.UUID) -> Conversation | None:
    """The conversation of these two people, whichever of them started it."""
    return db.scalar(
        select(Conversation).where(
            or_(
                and_(Conversation.starter_id == a, Conversation.provider_id == b),
                and_(Conversation.starter_id == b, Conversation.provider_id == a),
            )
        )
    )


# ---- starting ---------------------------------------------------------------------------------


def start_conversation(
    db: Session, settings: Settings, starter: Person, provider_id: uuid.UUID
) -> tuple[Conversation, bool]:
    """The conversation with this provider; `(conversation, created)`."""
    if provider_id == starter.id:
        raise ApiError(422, "cannot_message_self", "You cannot write to yourself")
    lock_people(db, [starter.id, provider_id])
    visible_provider(db, provider_id)  # 404 for anyone a searcher may not see
    existing = _between(db, starter.id, provider_id)
    if existing is not None:
        if _state(db, existing.id, "provider").blocked:
            raise ApiError(403, "chat_blocked", "You cannot write to this person")
        return existing, False
    started_today = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.starter_id == starter.id,
            Conversation.created_at > now() - timedelta(days=1),
        )
    )
    if (started_today or 0) >= settings.chat_max_new_conversations_per_day:
        raise ApiError(
            429,
            "chat_new_conversation_limit",
            "You have started many conversations today. Try again tomorrow.",
        )
    conversation = Conversation(starter_id=starter.id, provider_id=provider_id)
    db.add(conversation)
    try:
        db.flush()
    except IntegrityError:  # a second request for the same pair won the race
        db.rollback()
        found = _between(db, starter.id, provider_id)
        if found is None:
            raise
        return found, False
    db.add_all(
        [
            ConversationState(conversation_id=conversation.id, side="starter"),
            ConversationState(conversation_id=conversation.id, side="provider"),
        ]
    )
    db.flush()
    return conversation, True


# ---- sending ----------------------------------------------------------------------------------


def clean_body(body: str) -> str:
    text = body.strip()
    if not text:
        raise ApiError(422, "chat_message_empty", "A message cannot be empty")
    if len(text) > MAX_MESSAGE_CHARS:
        raise ApiError(422, "chat_message_too_long", "This message is too long")
    if _CONTROL.search(text):
        raise ApiError(
            422, "chat_message_invalid", "This message has characters that are not allowed"
        )
    return text


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        seq=message.seq,
        conversation_id=message.conversation_id,
        sender_side=message.sender_side,
        body=message.body,
        created_at=message.created_at,
    )


def _sent_in_last_minute(db: Session, person_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.sender_id == person_id, Message.created_at > now() - timedelta(minutes=1)
            )
        )
        or 0
    )


def send_message(
    db: Session,
    settings: Settings,
    conversation: Conversation,
    side: str,
    sender: Person,
    client_message_id: uuid.UUID,
    body: str,
) -> tuple[Message, bool]:
    """Store a message; `(message, created)`. A repeated `client_message_id` returns the stored
    message and `created=False`, so a retry after a lost answer is safe."""
    # One sender's sends are counted and stored one at a time, so the per-minute limit holds
    # under parallel requests (people first, as everywhere).
    lock_people(db, [sender.id])
    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sender_side == side,
            Message.client_message_id == client_message_id,
        )
    )
    if existing is not None:
        return existing, False
    text = clean_body(body)
    recipient = db.get(Person, other_id(conversation, side))
    if _state(db, conversation.id, "provider").blocked:
        raise ApiError(403, "chat_blocked", "You cannot write to this person")
    if recipient is None or not _is_open(recipient):
        raise ApiError(409, "chat_closed", "This person can no longer be written to")
    if _sent_in_last_minute(db, sender.id) >= settings.chat_max_messages_per_minute:
        raise ApiError(429, "chat_rate_limited", "You are sending messages too fast")
    message = Message(
        conversation_id=conversation.id,
        sender_side=side,
        sender_id=sender.id,
        body=text,
        client_message_id=client_message_id,
    )
    db.add(message)
    try:
        db.flush()
    except IntegrityError:  # the same retry arrived twice at once
        db.rollback()
        stored = db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.sender_side == side,
                Message.client_message_id == client_message_id,
            )
        )
        if stored is None:
            raise
        return stored, False
    db.refresh(message)  # the server's time and the sequence number
    conversation.last_message_at = message.created_at
    # The sender has seen their own message.
    _advance(db, conversation.id, side, message.seq)
    notify(
        db,
        {
            "kind": "message",
            "conversation_id": str(conversation.id),
            "seq": message.seq,
            # The recipient, and the sender's other devices.
            "people": [str(recipient.id), str(sender.id)],
        },
    )
    push.enqueue(
        db,
        settings,
        recipient,
        conversation,
        "provider" if side == "starter" else "starter",
        message.seq,
    )
    return message, True


# ---- reading ----------------------------------------------------------------------------------


def _advance(db: Session, conversation_id: uuid.UUID, side: str, seq: int) -> bool:
    """Move the side's read and delivered marks up to `seq`, never down, in one statement so that
    two devices acting at once cannot move a mark backwards. True when the read mark moved."""
    state = _state(db, conversation_id, side)  # exists
    moved = cast(
        "CursorResult[Any]",
        db.execute(
            update(ConversationState)
            .where(
                ConversationState.conversation_id == conversation_id,
                ConversationState.side == side,
                ConversationState.last_read_seq < seq,
            )
            .values(
                last_read_seq=seq, delivered_seq=func.greatest(ConversationState.delivered_seq, seq)
            )
        ),
    ).rowcount
    db.execute(
        update(ConversationState)
        .where(
            ConversationState.conversation_id == conversation_id,
            ConversationState.side == side,
            ConversationState.delivered_seq < seq,
        )
        .values(delivered_seq=seq)
    )
    db.refresh(state)  # the statements above changed the row behind the object
    return moved > 0


def mark_read(db: Session, conversation: Conversation, side: str, up_to_seq: int) -> int:
    """Move the side's read mark forward only; returns the mark."""
    newest = (
        db.scalar(select(func.max(Message.seq)).where(Message.conversation_id == conversation.id))
        or 0
    )
    target = min(up_to_seq, newest)
    if _advance(db, conversation.id, side, target):
        notify(
            db,
            {
                "kind": "read",
                "conversation_id": str(conversation.id),
                "up_to_seq": target,
                "side": side,
                # The other person (read ticks), and this person's other devices.
                "people": [
                    str(other_id(conversation, side)),
                    str(conversation.starter_id if side == "starter" else conversation.provider_id),
                ],
            },
        )
    return _state(db, conversation.id, side).last_read_seq


def mark_delivered(db: Session, conversation: Conversation, side: str, up_to_seq: int) -> None:
    """The side's app received messages up to `up_to_seq` (never down, never beyond the newest)."""
    newest = (
        db.scalar(select(func.max(Message.seq)).where(Message.conversation_id == conversation.id))
        or 0
    )
    target = min(up_to_seq, newest)
    state = _state(db, conversation.id, side)
    if target <= state.delivered_seq:
        return
    db.execute(
        update(ConversationState)
        .where(
            ConversationState.conversation_id == conversation.id,
            ConversationState.side == side,
        )
        .values(delivered_seq=func.greatest(ConversationState.delivered_seq, target))
    )
    db.refresh(state)
    notify(
        db,
        {
            "kind": "delivered",
            "conversation_id": str(conversation.id),
            "up_to_seq": target,
            "side": side,
            "people": [str(other_id(conversation, side))],
        },
    )


def messages_page(
    db: Session, conversation: Conversation, before_seq: int | None, limit: int
) -> list[Message]:
    query = select(Message).where(Message.conversation_id == conversation.id)
    if before_seq is not None:
        query = query.where(Message.seq < before_seq)
    return list(db.scalars(query.order_by(Message.seq.desc()).limit(limit)).all())


def update_settings(
    db: Session, conversation: Conversation, side: str, *, muted: bool | None, blocked: bool | None
) -> ConversationState:
    state = _state(db, conversation.id, side)
    if blocked is not None:
        if side != "provider":
            raise ApiError(403, "chat_not_allowed", "Only the person written to can block")
        state.blocked = blocked
    if muted is not None:
        state.muted = muted
    return state


# ---- lists ------------------------------------------------------------------------------------


def _unread_query(person_id: uuid.UUID, *columns: Any) -> Select[Any]:
    """Messages from the other side after the person's read mark (the base of both counts)."""
    mine = case((Conversation.starter_id == person_id, "starter"), else_="provider")
    return (
        select(*columns)
        .select_from(Conversation)
        .join(Message, Message.conversation_id == Conversation.id)
        .join(
            ConversationState,
            and_(
                ConversationState.conversation_id == Conversation.id,
                ConversationState.side == mine,
            ),
        )
        .where(
            or_(Conversation.starter_id == person_id, Conversation.provider_id == person_id),
            Message.sender_side != mine,
            Message.seq > ConversationState.last_read_seq,
        )
    )


def _unread_by_conversation(
    db: Session, person_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Unread messages per conversation, for the conversations on a page."""
    query = (
        _unread_query(person_id, Conversation.id, func.count(Message.id))
        .where(Conversation.id.in_(ids))
        .group_by(Conversation.id)
    )
    return {row[0]: row[1] for row in db.execute(query).all()}


def unread_total(db: Session, person_id: uuid.UUID) -> int:
    """All unread messages of the person, summed in the database."""
    return db.scalar(_unread_query(person_id, func.count(Message.id))) or 0


def list_conversations(
    db: Session, person: Person, offset: int, limit: int, *, only: uuid.UUID | None = None
) -> tuple[list[ConversationOut], int]:
    where = or_(Conversation.starter_id == person.id, Conversation.provider_id == person.id)
    if only is not None:
        where = and_(where, Conversation.id == only)
    total = db.scalar(select(func.count()).select_from(Conversation).where(where)) or 0
    rows = db.scalars(
        select(Conversation)
        .where(where)
        .order_by(
            func.coalesce(Conversation.last_message_at, Conversation.created_at).desc(),
            Conversation.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    ids = [c.id for c in rows]
    unread = _unread_by_conversation(db, person.id, ids) if ids else {}
    last: dict[uuid.UUID, str] = {}
    if ids:
        for conversation_id, body in db.execute(
            select(Message.conversation_id, Message.body)
            .where(Message.conversation_id.in_(ids))
            .distinct(Message.conversation_id)
            .order_by(Message.conversation_id, Message.seq.desc())
        ).all():
            last[conversation_id] = body
    states = (
        {
            (s.conversation_id, s.side): s
            for s in db.scalars(
                select(ConversationState).where(ConversationState.conversation_id.in_(ids))
            ).all()
        }
        if ids
        else {}
    )
    people = (
        {
            p.id: p
            for p in db.scalars(
                select(Person).where(
                    Person.id.in_({other_id(c, side_of(c, person.id) or "starter") for c in rows})
                )
            ).all()
        }
        if rows
        else {}
    )
    items: list[ConversationOut] = []
    for c in rows:
        side = side_of(c, person.id) or "starter"
        other = people.get(other_id(c, side))
        mine = states.get((c.id, side))
        provider_state = states.get((c.id, "provider"))
        preview = last.get(c.id)
        items.append(
            ConversationOut(
                id=c.id,
                my_side=side,
                other=OtherPerson(
                    id=other_id(c, side),
                    full_name=other.full_name
                    if other is not None and other.closed_at is None
                    else None,
                    closed=other is None or other.closed_at is not None,
                ),
                last_message_preview=preview[:PREVIEW_CHARS] if preview else None,
                last_message_at=c.last_message_at,
                unread_count=unread.get(c.id, 0),
                muted=bool(mine and mine.muted),
                blocked=bool(side == "provider" and provider_state and provider_state.blocked),
            )
        )
    return items, total
