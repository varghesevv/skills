import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.church import IdName, NameRef


class Voucher(BaseModel):
    name: str
    church_name: str
    live: bool  # a withdrawn vouch, or one by someone no longer admitted, does not count


class ApplicantRow(BaseModel):
    id: uuid.UUID
    full_name: str
    status: str  # pending, or searcher for someone who asks to become a provider
    requested_status: str | None
    home_group: IdName
    applied_at: datetime
    vouch_count: int  # live vouches
    vouchers: list[Voucher]
    # Whether the caller may admit them as a provider now (a live vouch from someone besides the
    # caller). Admitting as a searcher needs no vouch, so there is no flag for it.
    can_admit_as_provider: bool


class ApplicantList(BaseModel):
    items: list[ApplicantRow]
    total: int


class MemberRow(BaseModel):
    id: uuid.UUID
    full_name: str
    status: str
    home_group: IdName | None
    status_set_by: NameRef | None
    flagged_for_recheck: bool


class MemberList(BaseModel):
    items: list[MemberRow]
    total: int


class RevokedRow(BaseModel):
    id: uuid.UUID
    full_name: str
    removed_from: IdName | None  # the home group they were removed from
    revoked_by: NameRef | None
    revoked_at: datetime | None


class RevokedList(BaseModel):
    items: list[RevokedRow]
    total: int


class FlaggedRow(BaseModel):
    id: uuid.UUID
    full_name: str
    status: str
    home_group: IdName | None
    status_set_by: NameRef | None


class FlaggedList(BaseModel):
    items: list[FlaggedRow]
    total: int


class HistoryEntry(BaseModel):
    kind: str
    from_status: str | None
    to_status: str
    changed_by: NameRef | None  # none for a sign-up or a change by the operators
    at: datetime


class ChainLink(BaseModel):
    id: uuid.UUID
    full_name: str
    status: str


class PersonDetail(BaseModel):
    """One person in scope. This is the only response outside the reveal endpoint with a number."""

    id: uuid.UUID
    full_name: str
    mobile_number: str
    status: str
    requested_status: str | None
    church: IdName
    home_group: IdName | None  # for a revoked person, the group they were removed from
    status_set_by: NameRef | None
    flagged_for_recheck: bool
    applied_at: datetime
    history: list[HistoryEntry]  # newest first
    chain_of_trust: list[ChainLink]  # who set their status, then who set theirs, up to the OWNER
    vouches: list[Voucher]
    # As in the applicants list: whether the caller may admit them as a provider now.
    can_admit_as_provider: bool


class AdmitRequest(BaseModel):
    to: Literal["searcher", "provider"]


class AdmitResult(BaseModel):
    id: uuid.UUID
    status: str
    requested_status: str | None


Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0, le=100_000)]


class StatusRequest(BaseModel):
    """Revoke (`to` is `revoked`) or reinstate (a revoked person, `to` the new status and the
    home group they are placed in)."""

    to: Literal["revoked", "searcher", "provider"]
    home_group_id: uuid.UUID | None = None
    # Revoking a VERIFIER: the member who leads their group from now on. Without one the group
    # closes if the VERIFIER is its only member, and the revocation is refused otherwise.
    successor_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _group_only_for_reinstating(self) -> Self:
        if self.to == "revoked" and self.home_group_id is not None:
            raise ValueError("a revocation takes no home group")
        if self.to != "revoked" and self.home_group_id is None:
            raise ValueError("reinstating needs a home group")
        if self.to != "revoked" and self.successor_id is not None:
            raise ValueError("only a revocation has a successor")
        return self


class StatusResult(BaseModel):
    id: uuid.UUID
    status: str
    home_group_id: uuid.UUID | None
    flagged_for_recheck: bool
