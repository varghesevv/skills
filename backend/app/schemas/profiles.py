import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

from app.schemas.auth import Mobile, PersonName
from app.schemas.church import IdName
from app.schemas.common import LabelOut

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


class PublicRating(BaseModel):
    """A rating as others see it. The rater is not shown."""

    rating: int
    comment: str | None
    rated_on: datetime


class GivenRating(BaseModel):
    """A rating a person gave, with the provider's name so they can recognise it."""

    id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str | None
    rating: int
    comment: str | None
    rated_on: datetime
    updated_at: datetime | None


class FreelancerPublic(BaseModel):
    """What a SEARCHER or above sees of a provider. Never the email or the mobile number."""

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
    church: IdName
    home_group: IdName
    unavailable: list[UnavailabilityOut]  # upcoming periods
    my_rating: GivenRating | None = None  # only for the person who rated this provider


class RatingCreate(BaseModel):
    provider_id: uuid.UUID
    rating: Annotated[int, Field(ge=1, le=10)]
    comment: Annotated[str, Field(max_length=2000)] | None = None


class RatingUpdate(BaseModel):
    rating: Annotated[int, Field(ge=1, le=10)]
    comment: Annotated[str, Field(max_length=2000)] | None = None


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
