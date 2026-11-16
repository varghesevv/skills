import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, WebSocket, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.chat import rules, ws
from app.chat.runtime import ChatRuntime, SessionFactory
from app.core.config import Settings, get_settings
from app.core.db import get_session, get_session_factory
from app.models.church import Person
from app.schemas.chat import (
    ConversationOut,
    MessageOut,
    ReadMark,
    SendMessage,
    SettingsUpdate,
    StartConversation,
    UnreadOut,
)
from app.schemas.common import Page, Pagination, pagination

router = APIRouter(prefix="/chat", tags=["chat"])

# Anyone admitted (SEARCHER or above) may chat: a starter must be one, a provider is above.
Member = Annotated[Person, Depends(current_person("searcher"))]


def _conversation_out(db: Session, person: Person, conversation_id: uuid.UUID) -> ConversationOut:
    items, _ = rules.list_conversations(db, person, 0, 1, only=conversation_id)
    return items[0]


@router.post("/conversations")
def start(
    body: StartConversation,
    response: Response,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationOut:
    """Start a conversation with a provider, or return the one that exists (`200`)."""
    conversation, created = rules.start_conversation(db, settings, person, body.provider_id)
    db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _conversation_out(db, person, conversation.id)


@router.get("/conversations")
def conversations(
    person: Member,
    db: Annotated[Session, Depends(get_session)],
    paging: Pagination = Depends(pagination),
) -> Page[ConversationOut]:
    items, total = rules.list_conversations(db, person, paging.offset, paging.page_size)
    return Page[ConversationOut](
        items=items, total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/conversations/{conversation_id}/messages")
def messages(
    conversation_id: uuid.UUID,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> list[MessageOut]:
    """Newest first; `before_seq` is the cursor."""
    conversation, _side = rules.open_conversation(db, conversation_id, person)
    return [rules.message_out(m) for m in rules.messages_page(db, conversation, before_seq, limit)]


@router.post("/conversations/{conversation_id}/messages")
def send(
    conversation_id: uuid.UUID,
    body: SendMessage,
    response: Response,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageOut:
    """Send a message. Idempotent: the same `client_message_id` returns the stored one (`200`)."""
    conversation, side = rules.open_conversation(db, conversation_id, person)
    message, created = rules.send_message(
        db, settings, conversation, side, person, body.client_message_id, body.body
    )
    db.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return rules.message_out(message)


@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read(
    conversation_id: uuid.UUID,
    body: ReadMark,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
) -> Response:
    conversation, side = rules.open_conversation(db, conversation_id, person)
    rules.mark_read(db, conversation, side, body.up_to_seq)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/conversations/{conversation_id}/settings")
def settings_update(
    conversation_id: uuid.UUID,
    body: SettingsUpdate,
    person: Member,
    db: Annotated[Session, Depends(get_session)],
) -> ConversationOut:
    conversation, side = rules.open_conversation(db, conversation_id, person)
    rules.update_settings(db, conversation, side, muted=body.muted, blocked=body.blocked)
    db.commit()
    return _conversation_out(db, person, conversation.id)


@router.get("/unread")
def unread(person: Member, db: Annotated[Session, Depends(get_session)]) -> UnreadOut:
    return UnreadOut(total=rules.unread_total(db, person.id))


@router.websocket("/ws")
async def socket(
    websocket: WebSocket,
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Live events (ADR-0014): the first frame must be `{"type":"auth","token":...}`."""
    runtime: ChatRuntime | None = getattr(websocket.app.state, "chat", None)
    if runtime is None:  # the API started without chat (no database yet)
        await websocket.close(code=1013)
        return
    await ws.serve(websocket, runtime, factory, settings)
