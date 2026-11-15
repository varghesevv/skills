"""Small helpers for API tests: labels, and a token of an older kind that opens nothing."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal, create_access_token
from app.models.labels import Label

API = "/api/v1"


@dataclass
class Actor:
    id: uuid.UUID
    headers: dict[str, str]


def older_actor(role: str = "workhost") -> Actor:
    """A token of an account of the older kind. There are no such accounts any more, so it opens
    nothing: every endpoint answers 401 `invalid_token`."""
    account_id = uuid.uuid4()
    token, _ = create_access_token(
        Principal(role, account_id),
        secret=get_settings().require_jwt_secret(),
        lifetime_minutes=5,
    )
    return Actor(account_id, {"Authorization": f"Bearer {token}"})


def label_id(session: Session, label_type: str, name: str) -> str:
    found = session.scalar(
        select(Label.id).where(Label.label_type == label_type, Label.label_name == name)
    )
    assert found is not None, f"seed label {label_type}/{name} is missing"
    return str(found)
