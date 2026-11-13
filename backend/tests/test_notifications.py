"""The in-app notification list: what is shown, who sees it, reading, and retention."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Notification, Person
from app.services import notifications
from tests.api_helpers import API
from tests.test_person_auth import Member, add_member, bearer, login
from tests.trust_helpers import World

pytestmark = pytest.mark.db

URL = f"{API}/me/notifications"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def headers_of(client: TestClient, member: Member) -> dict[str, str]:
    return bearer(login(client, member))


def note(
    session: Session, to: Member, kind: str, about: Member | None = None, **extra: Any
) -> Notification:
    row = Notification(
        person_id=to.person.id,
        kind=kind,
        subject_id=about.person.id if about else None,
        **extra,
    )
    session.add(row)
    session.flush()
    return row


def listing(client: TestClient, member: Member, **params: Any) -> Any:
    return client.get(URL, headers=headers_of(client, member), params=params)


def test_the_list_is_mine_newest_first_with_the_subject_and_a_badge(
    client: TestClient, session: Session, world: World
) -> None:
    me = add_member(world, "pending")
    other = add_member(world, "searcher")
    a, b = add_member(world, "searcher"), add_member(world, "provider")
    note(session, me, "vouch_received", a, created_at=datetime.now(UTC) - timedelta(hours=2))
    newer = note(
        session, me, "vouch_received", b, created_at=datetime.now(UTC) - timedelta(hours=1)
    )
    note(session, other, "vouch_received", a)
    body = listing(client, me).json()
    assert body["total"] == 2 and body["unread_count"] == 2
    assert body["items"][0]["id"] == str(newer.id)
    assert body["items"][0]["subject"] == {"id": str(b.person.id), "name": b.person.full_name}
    assert body["items"][0]["read"] is False
    assert "mobile" not in str(body) and "email" not in str(body)


def test_paging_and_the_unread_filter(client: TestClient, session: Session, world: World) -> None:
    me = add_member(world, "searcher")
    for _ in range(3):
        note(session, me, "admitted")
    note(session, me, "admitted", read_at=datetime.now(UTC))
    page = listing(client, me, limit=2, offset=1).json()
    assert len(page["items"]) == 2 and page["total"] == 4
    unread = listing(client, me, unread="true").json()
    assert unread["total"] == 3 and unread["unread_count"] == 3
    assert all(not i["read"] for i in unread["items"])
    assert listing(client, me, limit=101).status_code == 422
    assert listing(client, me, offset=-1).status_code == 422


def test_a_closed_subject_has_no_name_left(
    client: TestClient, session: Session, world: World
) -> None:
    me = add_member(world, "pending")
    gone = add_member(world, "searcher")
    note(session, me, "vouch_received", gone)
    session.execute(
        update(Person)
        .where(Person.id == gone.person.id)
        .values(
            closed_at=datetime.now(UTC),
            home_group_id=None,
            full_name=None,
            email=None,
            mobile_number=None,
            password_hash=None,
        )
    )
    item = listing(client, me).json()["items"][0]
    assert item["subject"] == {"id": str(gone.person.id), "name": ""}


def test_reading_one_or_all(client: TestClient, session: Session, world: World) -> None:
    me = add_member(world, "pending")
    other = add_member(world, "searcher")
    first, second = note(session, me, "admitted"), note(session, me, "admitted")
    theirs = note(session, other, "admitted")
    headers = headers_of(client, me)
    assert client.post(f"{URL}/{first.id}/read", headers=headers).status_code == 204
    assert (
        client.post(f"{URL}/{first.id}/read", headers=headers).status_code == 204
    )  # twice is fine
    assert listing(client, me).json()["unread_count"] == 1
    # Someone else's and an unknown one are the same answer, and change nothing.
    mine_gone = client.post(f"{URL}/{theirs.id}/read", headers=headers)
    unknown = client.post(f"{URL}/00000000-0000-4000-8000-000000000000/read", headers=headers)
    assert mine_gone.status_code == unknown.status_code == 404 and mine_gone.text == unknown.text
    session.refresh(theirs)
    assert theirs.read_at is None
    assert client.post(f"{URL}/read-all", headers=headers).status_code == 204
    assert listing(client, me).json()["unread_count"] == 0
    session.refresh(theirs)
    assert theirs.read_at is None  # read-all is only mine
    session.refresh(second)
    assert second.read_at is not None


def test_who_may_read_them(client: TestClient, world: World) -> None:
    assert listing(client, add_member(world, "pending")).status_code == 200
    assert listing(client, add_member(world, "provider")).status_code == 200
    assert client.get(URL).status_code == 401
    revoked = add_member(world, "revoked", last_home_group_id=world.group.id)
    response = listing(client, revoked)
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_revoked"


def test_the_events_so_far_all_write_a_known_kind(
    client: TestClient, session: Session, world: World
) -> None:
    leader = add_member(world, "verifier")
    group_id = leader.person.home_group_id
    signed_up = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "New Applicant",
            "email": f"applicant-{secrets.token_hex(4)}@example.com",
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": secrets.token_urlsafe(16),
            "requested_status": "searcher",
            "home_group_id": str(group_id),
        },
    )
    assert signed_up.status_code == 201
    applicant_id = signed_up.json()["id"]
    voucher = add_member(world, "searcher")
    applicant = session.get(Person, applicant_id)
    assert applicant is not None
    link = client.post(
        f"{API}/me/vouch-link", headers=_headers_for(client, session, applicant)
    ).json()["token"]
    client.post(
        f"{API}/vouch-links/vouch", headers=headers_of(client, voucher), json={"token": link}
    )
    client.post(
        f"{API}/verifier/people/{applicant_id}/admit",
        headers=headers_of(client, leader),
        json={"to": "searcher"},
    )
    written = {n.kind for n in session.scalars(select(Notification))}
    assert written == set(notifications.KINDS)


def _headers_for(client: TestClient, session: Session, person: Person) -> dict[str, str]:
    from app.core.security import hash_password

    password = secrets.token_urlsafe(16)
    person.password_hash = hash_password(password)
    session.flush()
    member = Member(person, password)
    return headers_of(client, member)


def test_retention_deletes_only_what_is_old(session: Session, world: World) -> None:
    me = add_member(world, "searcher")
    now = datetime.now(UTC)
    old = note(session, me, "admitted", created_at=now - timedelta(days=400))
    recent = note(session, me, "admitted", created_at=now - timedelta(days=100))
    deleted = notifications.purge_older_than(session, now - timedelta(days=360))
    assert deleted == 1
    assert session.get(Notification, old.id) is None
    assert session.get(Notification, recent.id) is not None
