import uuid

from pydantic import BaseModel


class SearchSkill(BaseModel):
    name: str
    level: str | None = None


class SearchResult(BaseModel):
    """A freelancer in search results. Never contains email or mobile number."""

    id: uuid.UUID
    nationality: str | None
    primary_language: str | None
    whatsapp_availability: bool
    rate_per_hour: float | None
    rate_currency: str | None
    is_rate_negotiable: bool
    average_rating: float | None
    rating_count: int
    vouch_count: int  # organisations with an approved, active vouch
    skills: list[SearchSkill]
    languages: list[str]
    timings: list[str]
    nativity: list[str]
