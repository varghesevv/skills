import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, SecretStr

UserType = Literal["freelancer", "workhost", "organisation", "admin"]

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
_MOBILE = re.compile(r"^\+?[0-9]{7,15}$")


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _check_mobile(value: str) -> str:
    value = re.sub(r"[ -]", "", value)
    if not _MOBILE.match(value):
        raise ValueError("mobile number must be 7 to 15 digits, optionally starting with +")
    return value


Email = Annotated[EmailStr, AfterValidator(_normalise_email)]
Mobile = Annotated[str, AfterValidator(_check_mobile)]
# SecretStr keeps passwords out of repr() and logs.
NewPassword = Annotated[
    SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]


class RegisterBase(BaseModel):
    email: Email
    mobile_number: Mobile
    password: NewPassword


class FreelancerRegister(RegisterBase):
    nationality: Annotated[str, Field(max_length=100)] | None = None
    primary_language: Annotated[str, Field(max_length=100)] | None = None
    whatsapp_availability: bool = False


class WorkHostRegister(RegisterBase):
    pass


class OrganisationRegister(RegisterBase):
    org_name: Annotated[str, Field(min_length=2, max_length=200)]


class RegisterResponse(BaseModel):
    id: uuid.UUID
    user_type: UserType
    email: str
    # Organisations start as "pending" until an admin approves them; empty for other users.
    approval_status: str | None = None


class LoginRequest(BaseModel):
    email: Email
    # Not length-checked: a wrong password must be a normal 401, never a validation hint.
    password: Annotated[SecretStr, Field(max_length=1024)]
    user_type: UserType


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds until the access token expires


class RefreshRequest(BaseModel):
    refresh_token: Annotated[str, Field(min_length=10, max_length=500)]


class ForgotPasswordRequest(BaseModel):
    email: Email
    user_type: UserType


class ResetPasswordRequest(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=500)]
    new_password: NewPassword


class MeResponse(BaseModel):
    id: uuid.UUID
    user_type: UserType
    email: str
    mobile_number: str
    org_name: str | None = None
    approval_status: str | None = None
    created_at: datetime


class OrganisationSummary(BaseModel):
    id: uuid.UUID
    org_name: str
    email: str
    mobile_number: str
    approval_status: str
    created_at: datetime


class OrganisationPage(BaseModel):
    items: list[OrganisationSummary]
    total: int
    page: int
    page_size: int
