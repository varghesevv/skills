import uuid

from pydantic import BaseModel

from app.schemas.church import IdName


class SearchSkill(BaseModel):
    name: str
    level: str | None = None


class SearchResult(BaseModel):
    """A provider in search results. Never contains email or mobile number."""

    id: uuid.UUID
    full_name: str | None
    church: IdName
    home_group: IdName
    nationality: str | None
    primary_language: str | None
    whatsapp_availability: bool
    rate_per_hour: float | None
    rate_currency: str | None
    is_rate_negotiable: bool
    average_rating: float | None
    rating_count: int
    skills: list[SearchSkill]
    languages: list[str]
    timings: list[str]
    nativity: list[str]
