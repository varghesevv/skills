"""Who may be looked at, rated and revealed: open accounts of PROVIDER or above."""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models.church import Person
from app.models.enums import STATUS_RANK


def visible_provider(db: Session, provider_id: uuid.UUID, *, lock: bool = False) -> Person:
    """The provider with this id, or `404 not_found` when there is none a searcher may see.

    A person who does not exist, is closed, is revoked, or is below PROVIDER looks the same as one
    who does not exist, so nothing says whether they have an account.
    """
    person = db.get(Person, provider_id, with_for_update=lock)
    if (
        person is None
        or person.closed_at is not None
        or STATUS_RANK[person.status] < STATUS_RANK["provider"]
    ):
        raise ApiError(404, "not_found", "Provider not found")
    return person
