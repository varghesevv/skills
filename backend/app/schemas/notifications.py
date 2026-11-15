import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.church import IdName


class NotificationItem(BaseModel):
    id: uuid.UUID
    kind: str
    subject: IdName | None  # the person it is about (no name once their account is closed)
    created_at: datetime
    read: bool


class NotificationList(BaseModel):
    items: list[NotificationItem]
    total: int
    unread_count: int  # for a badge, whatever page or filter is shown
