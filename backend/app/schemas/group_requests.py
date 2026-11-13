import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.church import IdName

GroupName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


class GroupRequestCreate(BaseModel):
    group_name: GroupName


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


class GroupRequestCreated(BaseModel):
    """The request, or for an ADMIN or the OWNER the group, started at once."""

    request: GroupRequestOut
    group: IdName | None


class GroupStarted(BaseModel):
    group: IdName
