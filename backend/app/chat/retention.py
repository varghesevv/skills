"""What chat keeps and for how long (decision D-53)."""

import uuid
from collections.abc import Iterable

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.chat import Conversation
from app.models.church import Person


def delete_orphaned_conversations(db: Session, people: Iterable[uuid.UUID] | None = None) -> int:
    """Delete the conversations whose two people have both closed their accounts, with their
    messages, state, reports and pending pushes (the foreign keys cascade). With [people] only
    their conversations are looked at (an account was just closed); without, all of them (the
    worker's sweep, which also catches two accounts closed at the same moment, when neither
    closing could see the other's change). The caller commits."""
    starter, provider = aliased(Person), aliased(Person)
    orphaned = (
        select(Conversation.id)
        .join(starter, starter.id == Conversation.starter_id)
        .join(provider, provider.id == Conversation.provider_id)
        .where(starter.closed_at.is_not(None), provider.closed_at.is_not(None))
    )
    if people is not None:
        ids = list(people)
        orphaned = orphaned.where(
            or_(Conversation.starter_id.in_(ids), Conversation.provider_id.in_(ids))
        )
    result = db.execute(delete(Conversation).where(Conversation.id.in_(orphaned)))
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
