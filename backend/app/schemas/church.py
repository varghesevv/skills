import uuid
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import Mobile, PersonName


class ChurchSummary(BaseModel):
    id: uuid.UUID
    name: str


class ChurchList(BaseModel):
    items: list[ChurchSummary]


class HomeGroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    leader_name: str  # a name is needed to choose a group; nothing else about the leader


class HomeGroupList(BaseModel):
    items: list[HomeGroupSummary]


class NameRef(BaseModel):
    name: str


class IdName(BaseModel):
    id: uuid.UUID
    name: str


class PersonMeResponse(BaseModel):
    """The calling person, as `GET /me` shows them (the status is never in the token)."""

    id: uuid.UUID
    full_name: str
    email: str
    mobile_number: str
    status: str
    requested_status: str | None
    church: IdName
    home_group: IdName | None  # none for a revoked person
    leader: NameRef | None  # the leader of the home group
    status_set_by: NameRef | None  # none for a new applicant
    flagged_for_recheck: bool
    vouch_count: Annotated[int, Field(ge=0)]  # live vouches received


class PersonUpdate(BaseModel):
    full_name: PersonName | None = None
    mobile_number: Mobile | None = None

    @field_validator("full_name", "mobile_number", mode="before")
    @classmethod
    def _not_blank(cls, value: object) -> object:
        # An explicit null would clear a required field; leaving the key out keeps the value.
        if value is None:
            raise ValueError("must not be null; leave the field out to keep it")
        return value
