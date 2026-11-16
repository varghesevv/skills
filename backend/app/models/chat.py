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
from app.models.enums import CHAT_REPORT_REASONS, CHAT_SIDES, PUSH_PLATFORMS, PUSH_STATES, sql_in

MAX_MESSAGE_CHARS = 2000


class Conversation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversations"

    starter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_message_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("starter_id <> provider_id", name="not_self"),
        # One conversation per pair of people, whichever of them wrote first.
        Index(
            "uq_conversations_pair",
            text("least(starter_id, provider_id)"),
            text("greatest(starter_id, provider_id)"),
            unique=True,
        ),
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
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    # Chosen by the app, so a retry after a lost answer stores the message once.
    client_message_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("sender_side", CHAT_SIDES), name="side_valid"),
        CheckConstraint(f"length(body) BETWEEN 1 AND {MAX_MESSAGE_CHARS}", name="body_length"),
        UniqueConstraint(
            "conversation_id",
            "sender_side",
            "client_message_id",
            name="uq_messages_conversation_id_sender_side_client_message_id",
        ),
        Index("ix_messages_conversation_seq", "conversation_id", "seq"),
        Index("ix_messages_sender_time", "sender_id", "created_at"),
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


class ChatReport(UUIDPrimaryKeyMixin, Base):
    """A person reporting a conversation. The OWNER may then read it (each reading is logged)."""

    __tablename__ = "chat_reports"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    reported_by_side: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    handled_at: Mapped[datetime | None] = mapped_column()
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL")
    )

    __table_args__ = (
        CheckConstraint(sql_in("reported_by_side", CHAT_SIDES), name="side_valid"),
        CheckConstraint(sql_in("reason", CHAT_REPORT_REASONS), name="reason_valid"),
        CheckConstraint("(handled_at IS NULL) = (handled_by_id IS NULL)", name="handled_together"),
        # One open report per person and conversation: reporting again changes nothing.
        Index(
            "uq_chat_reports_open",
            "conversation_id",
            "reporter_id",
            unique=True,
            postgresql_where=text("handled_at IS NULL"),
        ),
        Index("ix_chat_reports_created", "created_at"),
    )


class ChatReportView(UUIDPrimaryKeyMixin, Base):
    """Each time the OWNER read a reported conversation: who and when, never what was read."""

    __tablename__ = "chat_report_views"

    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_reports.id", ondelete="CASCADE"))
    viewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    viewed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index(None, "report_id"),)


class DeviceToken(UUIDPrimaryKeyMixin, Base):
    """A phone's push address (S8.5). Unique: a token belongs to one person at a time."""

    __tablename__ = "device_tokens"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(512))
    platform: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint(sql_in("platform", PUSH_PLATFORMS), name="platform_valid"),
        CheckConstraint("length(token) > 0", name="token_not_empty"),
        UniqueConstraint("token", name="uq_device_tokens_token"),
        Index("ix_device_tokens_person", "person_id"),
    )


class PushOutbox(UUIDPrimaryKeyMixin, Base):
    """A push waiting for its time (ADR-0014). One pending row per person and conversation: more
    messages in the wait only raise `message_count` and `last_seq`. The worker cancels the row when
    the person has already received the message, and otherwise sends one generic push."""

    __tablename__ = "push_outbox"

    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    side: Mapped[str] = mapped_column(String(10))  # the recipient's side of the conversation
    last_seq: Mapped[int] = mapped_column(BigInteger)
    message_count: Mapped[int] = mapped_column(default=1)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    send_after: Mapped[datetime]
    state: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    finished_at: Mapped[datetime | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(20))  # why it was cancelled or failed

    __table_args__ = (
        CheckConstraint(sql_in("side", CHAT_SIDES), name="side_valid"),
        CheckConstraint(sql_in("state", PUSH_STATES), name="state_valid"),
        Index(
            "uq_push_outbox_pending",
            "person_id",
            "conversation_id",
            unique=True,
            postgresql_where=text("state = 'pending'"),
        ),
        Index("ix_push_outbox_due", "send_after", postgresql_where=text("state = 'pending'")),
        Index("ix_push_outbox_finished", "finished_at"),
    )
