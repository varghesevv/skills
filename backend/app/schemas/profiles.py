import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

from app.schemas.auth import Mobile, PersonName
from app.schemas.common import LabelOut

Day = Literal["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
DAYS: tuple[str, ...] = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


# ---- freelancer -------------------------------------------------------------------------


class FreelancerUpdate(BaseModel):
    """Replaces the editable profile fields (PUT)."""

    full_name: PersonName | None = None  # left unchanged when omitted
    mobile_number: Mobile
    whatsapp_availability: bool = False
    nationality: Annotated[str, Field(max_length=100)] | None = None
    primary_language: Annotated[str, Field(max_length=100)] | None = None
    rate_per_hour: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)] | None = None
    rate_currency: str | None = None  # ISO 4217, for example AED
    is_rate_negotiable: bool = False

    @model_validator(mode="after")
    def _rate_and_currency_go_together(self) -> Self:
        if (self.rate_per_hour is None) != (self.rate_currency is None):
            raise ValueError("rate_per_hour and rate_currency must be given together")
        if self.rate_currency is not None and not _CURRENCY.match(self.rate_currency):
            raise ValueError("rate_currency must be a 3-letter ISO 4217 code in capitals")
        return self


class FreelancerLabelOut(BaseModel):
    label: LabelOut
    level: LabelOut | None = None  # only for skills


class FreelancerMe(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    mobile_number: str
    whatsapp_availability: bool
    nationality: str | None
    primary_language: str | None
    rate_per_hour: float | None
    rate_currency: str | None
    is_rate_negotiable: bool
    labels: list[FreelancerLabelOut]
    created_at: datetime


class LabelSelection(BaseModel):
    label_id: uuid.UUID
    level_label_id: uuid.UUID | None = None  # a skill_level label, only for skill labels


class LabelsUpdate(BaseModel):
    labels: list[LabelSelection]


class UnavailabilityIn(BaseModel):
    unavailable_from: AwareDatetime
    unavailable_to: AwareDatetime

    @model_validator(mode="after")
    def _from_before_to(self) -> Self:
        if self.unavailable_from >= self.unavailable_to:
            raise ValueError("unavailable_from must be before unavailable_to")
        return self


class UnavailabilityOut(BaseModel):
    id: uuid.UUID
    unavailable_from: datetime
    unavailable_to: datetime


class VouchOut(BaseModel):
    org_id: uuid.UUID
    org_name: str
    status: str
    is_active: bool
    created_at: datetime


class PublicRating(BaseModel):
    """A rating as others see it. The work host's identity is not shown."""

    rating: int
    comment: str | None
    rated_on: datetime


class VouchingOrg(BaseModel):
    org_id: uuid.UUID
    org_name: str


class GivenRating(BaseModel):
    """A rating a work host gave, with the freelancer's name so the host can recognise it."""

    id: uuid.UUID
    freelancer_id: uuid.UUID
    freelancer_name: str | None
    rating: int
    comment: str | None
    rated_on: datetime
    updated_at: datetime | None


class FreelancerPublic(BaseModel):
    """What work hosts, organisations and admins see. Never the email."""

    id: uuid.UUID
    full_name: str | None
    whatsapp_availability: bool
    nationality: str | None
    primary_language: str | None
    rate_per_hour: float | None
    rate_currency: str | None
    is_rate_negotiable: bool
    labels: list[FreelancerLabelOut]
    average_rating: float | None
    rating_count: int
    vouched_by: list[VouchingOrg]
    unavailable: list[UnavailabilityOut]  # upcoming periods
    my_rating: GivenRating | None = None  # only for the work host who rated this person


# ---- work host --------------------------------------------------------------------------


class WorkHostUpdate(BaseModel):
    full_name: PersonName | None = None  # left unchanged when omitted
    mobile_number: Mobile
    available_days: list[Day] = []


class WorkHostMe(BaseModel):
    id: uuid.UUID
    full_name: str | None
    email: str
    mobile_number: str
    available_days: list[Day]
    created_at: datetime


class RatingCreate(BaseModel):
    freelancer_id: uuid.UUID
    rating: Annotated[int, Field(ge=1, le=10)]
    comment: Annotated[str, Field(max_length=2000)] | None = None


class RatingUpdate(BaseModel):
    rating: Annotated[int, Field(ge=1, le=10)]
    comment: Annotated[str, Field(max_length=2000)] | None = None


# ---- organisation -----------------------------------------------------------------------


class OrganisationUpdate(BaseModel):
    org_name: Annotated[str, Field(min_length=2, max_length=200)]
    mobile_number: Mobile


class OrganisationMe(BaseModel):
    id: uuid.UUID
    email: str
    org_name: str
    mobile_number: str
    approval_status: str
    created_at: datetime


class OrganisationBrief(BaseModel):
    """An approved organisation as listed in the directory (no contact details)."""

    id: uuid.UUID
    org_name: str


class VouchedFreelancer(BaseModel):
    freelancer_id: uuid.UUID
    full_name: str | None
    nationality: str | None
    primary_language: str | None
    status: str  # pending, approved or revoked
    is_active: bool
    created_at: datetime


# ---- labels -----------------------------------------------------------------------------


class LabelCreate(BaseModel):
    label_name: Annotated[str, Field(min_length=1, max_length=100)]
    label_type: Literal["skill", "language", "timing", "nativity", "skill_level"]


class LabelUpdate(BaseModel):
    label_name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    is_active: bool | None = None


class RevealRequest(BaseModel):
    """Why and how a work host asks for a mobile number. Both fields are hints for reports."""

    channel: Literal["dial", "show"]  # dial: the phone's dialler opens; show: shown on screen
    source: Literal["search", "detail"]  # the page the request came from
    searched_skills: list[Annotated[str, StringConstraints(max_length=100)]] = Field(
        default_factory=list, max_length=10
    )


class RevealedMobile(BaseModel):
    mobile_number: str
