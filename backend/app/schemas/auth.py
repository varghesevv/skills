import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, SecretStr, StringConstraints

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
_MOBILE = re.compile(r"^\+?[0-9]{7,15}$")


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def check_mobile(value: str) -> str:
    value = re.sub(r"[ -]", "", value)
    if not _MOBILE.match(value):
        raise ValueError("mobile number must be 7 to 15 digits, optionally starting with +")
    return value


Email = Annotated[EmailStr, AfterValidator(_normalise_email)]
# A person's name.
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
Mobile = Annotated[str, AfterValidator(check_mobile)]
# SecretStr keeps passwords out of repr() and logs.
NewPassword = Annotated[
    SecretStr, Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]


class LoginRequest(BaseModel):
    email: Email
    # Not length-checked: a wrong password must be a normal 401, never a validation hint.
    password: Annotated[SecretStr, Field(max_length=1024)]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - a label, not a secret
    expires_in: int  # seconds until the access token expires


class RefreshRequest(BaseModel):
    refresh_token: Annotated[str, Field(min_length=10, max_length=500)]


class ForgotPasswordRequest(BaseModel):
    email: Email


class ResetPasswordRequest(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=500)]
    new_password: NewPassword
