"""The whole identity journey of slice S2, through the real endpoints and a real database.

The web and the mobile app make exactly these calls (their own tests check the screens against
the same contract), so this is the check that the pieces fit: set up Skills, list the churches,
sign up two ways, log in, read the application, change it, reset a password, leave, and join
again.
"""

import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.models import Notification, Person, StatusChange
from app.services import rate_limit
from app.services.operators import create_first_owner
from tests.api_helpers import API

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    churches.limiter.reset()
    rate_limit.signup_limiter.reset()
    rate_limit.link_lookup_limiter.reset()


def bearer(response_json: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {response_json['access_token']}"}


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return bearer(response.json())


def test_the_identity_journey(
    client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    # 1. The operators set Skills up: the OWNER, their church and their home group.
    owner_password = secrets.token_urlsafe(16)
    create_first_owner(
        session,
        full_name="Olive Owner",
        email="olive@example.com",
        mobile_number="+971500000200",
        password=owner_password,
        church_name="Grace Church",
        group_name="Riverside",
    )
    owner_headers = login(client, "olive@example.com", owner_password)
    owner = client.get(f"{API}/me", headers=owner_headers).json()
    assert (owner["status"], owner["church"]["name"], owner["home_group"]["name"]) == (
        "owner",
        "Grace Church",
        "Riverside",
    )

    # 2. Nobody needs an account to see where they can join.
    listed = client.get(f"{API}/churches").json()["items"]
    assert [c["name"] for c in listed] == ["Grace Church"]
    groups = client.get(f"{API}/churches/{listed[0]['id']}/home-groups").json()["items"]
    assert [(g["name"], g["leader_name"]) for g in groups] == [("Riverside", "Olive Owner")]

    # 3. The leader gives out a link; one person joins by it, another by choosing the group.
    link = client.post(f"{API}/verifier/group-invitations", headers=owner_headers).json()
    info = client.post(f"{API}/group-invitations/lookup", json={"token": link["token"]})
    assert info.json()["home_group_name"] == "Riverside"

    ann_password = secrets.token_urlsafe(16)
    ann = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Ann Applicant",
            "email": "ann@example.com",
            "mobile_number": "+971500000201",
            "password": ann_password,
            "requested_status": "searcher",
            "home_group_id": groups[0]["id"],
        },
    )
    ben_password = secrets.token_urlsafe(16)
    ben = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Ben Applicant",
            "email": "ben@example.com",
            "mobile_number": "+971500000202",
            "password": ben_password,
            "requested_status": "provider",
            "invitation_token": link["token"],
        },
    )
    assert ann.status_code == ben.status_code == 201

    # 4. Both are pending in the leader's group, and the leader was told twice.
    for email, password, applied in (
        ("ann@example.com", ann_password, "searcher"),
        ("ben@example.com", ben_password, "provider"),
    ):
        me = client.get(f"{API}/me", headers=login(client, email, password)).json()
        assert me["status"] == "pending" and me["requested_status"] == applied
        assert me["home_group"]["name"] == "Riverside" and me["leader"] == {"name": "Olive Owner"}
        assert me["status_set_by"] is None and me["vouch_count"] == 0
    notes = session.scalars(select(Notification).where(Notification.person_id == owner["id"])).all()
    assert [n.kind for n in notes] == ["applicant_new", "applicant_new"]
    people = session.scalars(select(Person).where(Person.status == "pending")).all()
    assert {p.email for p in people} == {"ann@example.com", "ben@example.com"}
    history = session.scalars(select(StatusChange).where(StatusChange.kind == "signup")).all()
    assert len(history) == 2 and all(h.changed_by_id is None for h in history)

    # 5. An applicant changes what they apply for; a pending person cannot use leader features.
    ann_headers = login(client, "ann@example.com", ann_password)
    changed = client.put(
        f"{API}/me/application", headers=ann_headers, json={"requested_status": "provider"}
    )
    assert changed.json()["requested_status"] == "provider"
    assert client.get(f"{API}/verifier/group-invitations", headers=ann_headers).status_code == 403

    # 6. A forgotten password is reset, and only the new one works.
    with caplog.at_level("INFO"):
        client.post(f"{API}/auth/forgot-password", json={"email": "ben@example.com"})
    token = next(r.reset_link for r in caplog.records if hasattr(r, "reset_link")).split("token=")[
        1
    ]
    new_password = secrets.token_urlsafe(16)
    assert (
        client.post(
            f"{API}/auth/reset-password", json={"token": token, "new_password": new_password}
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"{API}/auth/login", json={"email": "ben@example.com", "password": ben_password}
        ).status_code
        == 401
    )
    assert login(client, "ben@example.com", new_password)

    # 7. An applicant leaves; the leader keeps their place (the OWNER cannot leave).
    left = client.request(
        "DELETE", f"{API}/me", headers=ann_headers, json={"password": ann_password}
    )
    assert left.status_code == 204
    assert (
        client.post(
            f"{API}/auth/login", json={"email": "ann@example.com", "password": ann_password}
        ).status_code
        == 401
    )
    refused = client.request(
        "DELETE", f"{API}/me", headers=owner_headers, json={"password": owner_password}
    )
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "leads_a_church")

    # 8. The same address can join again, as a new person.
    again = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Ann Again",
            "email": "ann@example.com",
            "mobile_number": "+971500000201",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": groups[0]["id"],
        },
    )
    assert again.status_code == 201
    assert len(session.scalars(select(Person).where(Person.email == "ann@example.com")).all()) == 1
