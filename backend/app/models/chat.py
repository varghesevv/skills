"""Chat between two people (ADR-0014): a conversation, its messages and each side's state.

The *starter* is the SEARCHER or above who found a provider; the *provider* is the open
PROVIDER or above they wrote to. One conversation per pair.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import CHAT_SIDES, sql_in

MAX_MESSAGE_CHARS = 2000


class Conversation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversations"

    starter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        UniqueConstraint("starter_id", "provider_id", name="pair"),
        CheckConstraint("starter_id <> provider_id", name="not_self"),
        Index("ix_conversations_starter_activity", "starter_id", text("last_message_at DESC")),
        Index("ix_conversations_provider_activity", "provider_id", text("last_message_at DESC")),
    )


class Message(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "messages"

    # Orders messages (a cursor); gaps are normal, it is not a count.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    sender_side: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)
    # Chosen by the app, so a retry after a lost answer stores the message once.
    client_message_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("sender_side", CHAT_SIDES), name="side_valid"),
        CheckConstraint(f"length(body) BETWEEN 1 AND {MAX_MESSAGE_CHARS}", name="body_length"),
        UniqueConstraint("conversation_id", "sender_side", "client_message_id", name="client_id"),
        Index("ix_messages_conversation_seq", "conversation_id", "seq"),
    )


class ConversationState(Base):
    """What one side of a conversation has seen, and its settings. Two rows per conversation."""

    __tablename__ = "conversation_state"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    side: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_read_seq: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    delivered_seq: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    muted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Only the provider side blocks; a block stops new messages in both directions.
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    __table_args__ = (CheckConstraint(sql_in("side", CHAT_SIDES), name="side_valid"),)
