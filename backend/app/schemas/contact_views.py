import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.church import IdName


class ContactViewOut(BaseModel):
    """One time a leader's screen showed a person's mobile number. Never the number itself."""

    id: uuid.UUID
    viewer: IdName
    person: IdName
    screen: str
    viewed_at: datetime


class ContactViewList(BaseModel):
    items: list[ContactViewOut]
    total: int
