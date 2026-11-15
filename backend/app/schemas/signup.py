import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.auth import Email, Mobile, NewPassword, PersonName

AppliedStatus = Literal["searcher", "provider"]


class SignupRequest(BaseModel):
    full_name: PersonName
    email: Email
    mobile_number: Mobile
    password: NewPassword
    requested_status: AppliedStatus
    # The home group chosen from the public list, or a group invitation link, which chooses the
    # church and the group by itself. Exactly one of the two.
    home_group_id: uuid.UUID | None = None
    invitation_token: Annotated[str, Field(min_length=10, max_length=500)] | None = None

    @model_validator(mode="after")
    def _one_way_in(self) -> Self:
        if (self.home_group_id is None) == (self.invitation_token is None):
            raise ValueError("give either home_group_id or invitation_token")
        return self


class SignupResponse(BaseModel):
    id: uuid.UUID
    status: Literal["pending"] = "pending"


class ApplicationUpdate(BaseModel):
    home_group_id: uuid.UUID | None = None
    requested_status: AppliedStatus | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if self.home_group_id is None and self.requested_status is None:
            raise ValueError("give home_group_id, requested_status or both")
        return self


class GroupInvitationLookup(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=500)]


class GroupInvitationInfo(BaseModel):
    """What the sign-up screen shows for an invitation link."""

    church_name: str
    home_group_name: str
    leader_name: str


class GroupInvitationCreated(BaseModel):
    id: uuid.UUID
    token: str  # shown once: only a hash is stored
    expires_at: datetime


class GroupInvitationSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    expires_at: datetime


class GroupInvitationList(BaseModel):
    items: list[GroupInvitationSummary]
