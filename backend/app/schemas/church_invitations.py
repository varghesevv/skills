import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.auth import Email, Mobile, NewPassword, PersonName

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Token = Annotated[str, Field(min_length=10, max_length=500)]


class ChurchInvite(BaseModel):
    church_name: Name
    email: Email


class ChurchInvitationCreated(BaseModel):
    id: uuid.UUID
    token: str  # shown once: only a hash is stored
    expires_at: datetime


class ChurchInvitationSummary(BaseModel):
    id: uuid.UUID
    church_name: str
    email: str
    created_at: datetime
    expires_at: datetime
    expired: bool


class ChurchInvitationList(BaseModel):
    items: list[ChurchInvitationSummary]
    total: int


class AdminInvitationLookup(BaseModel):
    token: Token


class AdminInvitationInfo(BaseModel):
    """What the person invited sees before accepting: the church, and where the invitation was
    sent (the domain only)."""

    church_name: str
    email_domain: str


class AdminInvitationAccept(BaseModel):
    token: Token
    full_name: PersonName
    mobile_number: Mobile
    password: NewPassword
    home_group_name: Name


class AdminAccepted(BaseModel):
    id: uuid.UUID
    church_id: uuid.UUID
    status: str


class ChurchClosed(BaseModel):
    id: uuid.UUID
    name: str
    closed_groups: int
    closed_accounts: int


class ChurchSummaryOwner(BaseModel):
    id: uuid.UUID
    name: str
    admin_name: str
    open: bool
    groups: int  # open home groups
    members: int  # open, not revoked
    revoked: int
    closed_at: datetime | None


class ChurchListOwner(BaseModel):
    items: list[ChurchSummaryOwner]
    total: int
