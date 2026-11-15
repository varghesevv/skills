import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.church import IdName


class MoveRequestCreate(BaseModel):
    home_group_id: uuid.UUID


class MoveAgreements(BaseModel):
    person: bool
    from_leader: bool
    to_leader: bool


class MoveRequestOut(BaseModel):
    id: uuid.UUID
    person: IdName
    from_group: IdName
    to_group: IdName
    agreed: MoveAgreements
    state: Literal["open", "completed", "cancelled"]
    created_at: datetime


class MoveRequestList(BaseModel):
    items: list[MoveRequestOut]
    total: int


class DirectMove(BaseModel):
    home_group_id: uuid.UUID


class Moved(BaseModel):
    person: IdName
    home_group: IdName
