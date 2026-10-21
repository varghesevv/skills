"""Small helpers for API tests: create users directly and get ready-to-use auth headers."""

import secrets
import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.labels import Label
from app.models.users import Organisation
from app.services.accounts import create_account

API = "/api/v1"


@dataclass
class Actor:
    id: uuid.UUID
    headers: dict[str, str]


def signup(
    client: TestClient,
    session: Session,
    user_type: str,
    email: str,
    *,
    approved: bool = True,
    **extra: object,
) -> Actor:
    password = secrets.token_urlsafe(16)
    if user_type == "organisation":
        extra.setdefault("org_name", "Test Org")
    account = create_account(
        session, user_type, email=email, mobile_number="+971500000099", password=password, **extra
    )
    if isinstance(account, Organisation) and approved:
        account.approval_status = "approved"
        session.commit()
    response = client.post(
        f"{API}/auth/login", json={"email": email, "password": password, "user_type": user_type}
    )
    if response.status_code != 200:
        return Actor(account.id, {})
    return Actor(account.id, {"Authorization": f"Bearer {response.json()['access_token']}"})


def label_id(session: Session, label_type: str, name: str) -> str:
    found = session.scalar(
        select(Label.id).where(Label.label_type == label_type, Label.label_name == name)
    )
    assert found is not None, f"seed label {label_type}/{name} is missing"
    return str(found)
