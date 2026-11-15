import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.signup import AppliedStatus


class VouchLinkToken(BaseModel):
    # Long enough to refuse a guess early; the real check is the hashed lookup.
    token: Annotated[str, Field(min_length=10, max_length=500)]


class VouchLinkState(BaseModel):
    """Whether the caller has a vouch link that still works. The token is never shown again."""

    active: bool
    expires_at: datetime | None


class VouchLinkCreated(BaseModel):
    token: str  # shown once: only a hash is stored
    expires_at: datetime


class VouchLinkInfo(BaseModel):
    """What the person opening a vouch link sees: who asks and what for, never a number."""

    applicant_name: str
    church_name: str
    home_group_name: str
    requested_status: AppliedStatus
    already_vouched: bool


class VouchCreated(BaseModel):
    id: uuid.UUID


class VouchReceived(BaseModel):
    id: uuid.UUID
    voucher_name: str
    church_name: str
    live: bool  # a withdrawn vouch, or one by someone no longer admitted, does not count
    created_at: datetime


class VouchReceivedList(BaseModel):
    items: list[VouchReceived]


class VouchGiven(BaseModel):
    id: uuid.UUID
    applicant_name: str
    applicant_status: str
    requested_status: str | None
    withdrawn: bool
    can_withdraw: bool  # until the applicant is admitted
    created_at: datetime


class VouchGivenList(BaseModel):
    items: list[VouchGiven]
