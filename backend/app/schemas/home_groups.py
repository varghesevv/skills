import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.church import IdName


class LeaderChange(BaseModel):
    """Replace the leader of a home group, or hand it on.

    `former_leader_status` is what a stepping-down VERIFIER becomes (`provider` or `searcher`), or
    `keep` for an ADMIN or the OWNER handing on their own group.
    """

    successor_id: uuid.UUID
    former_leader_status: Literal["provider", "searcher", "keep"]


class LeaderChanged(BaseModel):
    group: IdName
    leader: IdName


class AdminChange(BaseModel):
    """Replace the ADMIN of a church (the OWNER's own church changes only by a handover)."""

    successor_id: uuid.UUID  # a member of the church; becomes its ADMIN directly
    former_admin_status: Literal["provider", "searcher"]
    # If the old ADMIN leads a home group: the member who leads it from now on (it may be the new
    # ADMIN). Without one, the call is refused when the group has other members; an ADMIN who is
    # alone in it keeps leading it, as a VERIFIER.
    group_successor_id: uuid.UUID | None = None


class AdminChanged(BaseModel):
    church: IdName
    admin: IdName
    former_admin_keeps_leading: bool


class GroupClose(BaseModel):
    """The leader closes their own group, being its last member, by moving into another group."""

    move_to_group_id: uuid.UUID
    # `provider` or `searcher` for a VERIFIER (who no longer leads), `keep` for an ADMIN or OWNER.
    former_leader_status: Literal["provider", "searcher", "keep"]


class GroupClosed(BaseModel):
    closed_group: IdName
    joined_group: IdName
    status: str
