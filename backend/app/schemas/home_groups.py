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
