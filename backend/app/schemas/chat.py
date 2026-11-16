import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Side = Literal["starter", "provider"]


class StartConversation(BaseModel):
    provider_id: uuid.UUID


class SendMessage(BaseModel):
    client_message_id: uuid.UUID
    # Length is checked by the rules (after trimming) so the answer has a chat code.
    body: Annotated[str, Field(max_length=20_000)]


class ReadMark(BaseModel):
    up_to_seq: Annotated[int, Field(ge=0)]


class SettingsUpdate(BaseModel):
    muted: bool | None = None
    blocked: bool | None = None


class OtherPerson(BaseModel):
    id: uuid.UUID
    full_name: str | None  # empty once that account is closed
    closed: bool


class MessageOut(BaseModel):
    id: uuid.UUID
    seq: int
    conversation_id: uuid.UUID
    sender_side: Side
    body: str
    created_at: datetime


class ConversationOut(BaseModel):
    id: uuid.UUID
    my_side: Side
    other: OtherPerson
    last_message_preview: str | None
    last_message_at: datetime | None
    unread_count: int
    muted: bool
    blocked: bool  # the provider's own block; the starter is never told


class UnreadOut(BaseModel):
    total: int
