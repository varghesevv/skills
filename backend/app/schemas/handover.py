import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.church import IdName


class HandoverPropose(BaseModel):
    """The OWNER proposes to hand over to the ADMIN of another church."""

    new_owner_id: uuid.UUID
    # The members of the OWNER's own church and group who take over; each may be left out only
    # when nobody else is in the church (or the group), and the OWNER then keeps that role.
    successor_admin_id: uuid.UUID | None = None
    successor_leader_id: uuid.UUID | None = None
    # What the outgoing OWNER becomes when they keep neither role.
    former_owner_status: Literal["provider", "searcher"] = "provider"


class HandoverOut(BaseModel):
    id: uuid.UUID
    owner: IdName
    new_owner: IdName
    successor_admin: IdName | None
    successor_leader: IdName | None
    former_owner_status: str
    created_at: datetime


class HandoverCurrent(BaseModel):
    """The open request that concerns the caller, if there is one."""

    request: HandoverOut | None


class HandoverAccepted(BaseModel):
    owner: IdName  # the new OWNER
    former_owner: IdName
    former_owner_status: str  # what they are now
