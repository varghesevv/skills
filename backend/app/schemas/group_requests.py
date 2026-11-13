import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.church import IdName

GroupName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class GroupRequestCreate(BaseModel):
    group_name: GroupName
    # An ADMIN or the OWNER who lead a group now and start another at once: who leads the old one.
    successor_id: uuid.UUID | None = None


class GroupRequestApprove(BaseModel):
    # The requester leads a group now: the member who leads it from now on (without one the old
    # group closes if the requester is its only member, and approving is refused otherwise).
    successor_id: uuid.UUID | None = None


class GroupRequestOut(BaseModel):
    id: uuid.UUID
    group_name: str
    church: IdName
    requester: IdName
    state: str  # open, approved or declined
    created_at: datetime
    # The requester leads a home group now: approving needs a successor for it (roadmap 4.3).
    requester_leads_a_group: bool


class GroupRequestList(BaseModel):
    items: list[GroupRequestOut]
    total: int


class GroupRequestCreated(BaseModel):
    """The request, or for an ADMIN or the OWNER the group, started at once."""

    request: GroupRequestOut
    group: IdName | None


class GroupStarted(BaseModel):
    group: IdName
