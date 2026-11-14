"""The log of phone number views: what the OWNER reads, and its retention (decision O-03)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cli
from app.models import ContactView
from app.services import contact_views, notifications
from tests.api_helpers import API
from tests.test_admission import headers_of, leader, owner_member
from tests.test_person_auth import add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db

URL = f"{API}/owner/contact-views"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def view(client: TestClient, lead: Any, person_id: object) -> None:
    """A leader opens one person's page, which records a view."""
    response = client.get(f"{API}/verifier/people/{person_id}", headers=headers_of(client, lead))
    assert response.status_code == 200, response.text


def test_the_owner_reads_who_looked_at_whom_without_a_number(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    first = add_member(world, "searcher", group=group, full_name="Fay First")
    second = add_member(world, "provider", group=group, full_name="Sam Second")
    view(client, lead, first.person.id)
    view(client, lead, second.person.id)
    owner = owner_member(world)
    response = client.get(URL, headers=headers_of(client, owner))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    # (Both rows share a transaction's clock here, so only the set can be compared.)
    assert {row["person"]["name"] for row in body["items"]} == {"Sam Second", "Fay First"}
    assert {row["viewer"]["id"] for row in body["items"]} == {str(lead.person.id)}
    assert all(row["screen"] == "person" and row["viewed_at"] for row in body["items"])
    text = response.text
    for who in (first, second, lead):
        assert who.person.mobile_number not in text
        assert who.person.email not in text


def test_the_newest_view_comes_first(client: TestClient, session: Session, world: World) -> None:
    lead, group = leader(world)
    older = add_member(world, "searcher", group=group, full_name="Older View")
    newer = add_member(world, "searcher", group=group, full_name="Newer View")
    now = datetime.now(UTC)
    for member, age in ((older, 5), (newer, 1)):
        session.add(
            ContactView(
                viewer_id=lead.person.id,
                person_id=member.person.id,
                screen="person",
                viewed_at=now - timedelta(days=age),
            )
        )
    session.flush()
    items = client.get(URL, headers=headers_of(client, owner_member(world))).json()["items"]
    assert [row["person"]["name"] for row in items] == ["Newer View", "Older View"]


def test_the_log_is_filtered_by_viewer_and_by_person_and_paged(
    client: TestClient, world: World
) -> None:
    lead, group = leader(world)
    other, other_group = leader(world)
    a = add_member(world, "searcher", group=group)
    b = add_member(world, "searcher", group=other_group)
    view(client, lead, a.person.id)
    view(client, lead, a.person.id)
    view(client, other, b.person.id)
    owner = owner_member(world)
    headers = headers_of(client, owner)
    by_viewer = client.get(URL, headers=headers, params={"viewer_id": str(other.person.id)})
    assert by_viewer.json()["total"] == 1
    by_person = client.get(URL, headers=headers, params={"person_id": str(a.person.id)})
    assert by_person.json()["total"] == 2
    page = client.get(URL, headers=headers, params={"limit": 1, "offset": 2}).json()
    assert len(page["items"]) == 1 and page["total"] == 3
    assert client.get(URL, headers=headers, params={"limit": 101}).status_code == 422
    assert client.get(URL, headers=headers, params={"viewer_id": "nope"}).status_code == 422


@pytest.mark.parametrize("status", ["admin", "verifier", "provider", "searcher"])
def test_only_the_owner_reads_it(client: TestClient, world: World, status: str) -> None:
    member = add_member(world, status)
    assert client.get(URL, headers=headers_of(client, member)).status_code == 403


def test_it_needs_a_sign_in(client: TestClient) -> None:
    assert client.get(URL).status_code in (401, 403)


def test_a_closed_account_keeps_its_row_with_an_empty_name(
    client: TestClient, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group, full_name="Gone Person")
    view(client, lead, member.person.id)
    member.person.closed_at = datetime.now(UTC)
    member.person.full_name = None
    member.person.email = None
    member.person.mobile_number = None
    member.person.password_hash = None
    member.person.home_group_id = None
    session.flush()
    body = client.get(URL, headers=headers_of(client, owner_member(world))).json()
    assert body["total"] == 1
    assert body["items"][0]["person"] == {"id": str(member.person.id), "name": ""}


def test_retention_deletes_only_what_is_old(session: Session, world: World) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group)
    now = datetime.now(UTC)
    rows = {
        age: ContactView(
            viewer_id=lead.person.id,
            person_id=member.person.id,
            screen="person",
            viewed_at=now - timedelta(days=age),
        )
        for age in (400, 100)
    }
    session.add_all(rows.values())
    session.flush()
    deleted = contact_views.purge_older_than(session, now - timedelta(days=360))
    assert deleted == 1
    assert session.get(ContactView, rows[400].id) is None
    assert session.get(ContactView, rows[100].id) is not None


def test_the_command_deletes_by_the_calendar_months_it_is_given(
    monkeypatch: pytest.MonkeyPatch, session: Session, world: World
) -> None:
    lead, group = leader(world)
    member = add_member(world, "searcher", group=group)
    now = datetime.now(UTC)
    session.add_all(
        ContactView(
            viewer_id=lead.person.id,
            person_id=member.person.id,
            screen="person",
            viewed_at=notifications.months_before(now, months) - timedelta(days=1),
        )
        for months in (13, 11)
    )
    session.flush()

    class Bound:
        """The command opens its own session: give it the test's, which never commits for real."""

        def __call__(self, **_: object) -> "Bound":
            return self

        def __enter__(self) -> Session:
            return session

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(cli, "sessionmaker", Bound())
    monkeypatch.setattr(cli, "get_engine", lambda: None)
    assert cli.purge_contact_views(12) == 0
    left = session.scalar(select(func.count()).select_from(ContactView))
    assert left == 1  # the one of 13 months ago is gone, the one of 11 months stays
