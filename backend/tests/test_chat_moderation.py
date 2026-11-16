"""Reporting a conversation and the OWNER reading it (S8.4): only reported conversations are
readable, every reading is logged, and the report RP-10 counts them without names or text."""

import secrets
import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Person
from app.models.chat import ChatReport, ChatReportView
from app.reports.runner import build_report
from tests.api_helpers import API
from tests.test_admission import headers_of
from tests.test_chat_api import Pair, code
from tests.test_person_auth import Member, add_member
from tests.test_reports import params
from tests.trust_helpers import World

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture
def pair(client: TestClient, world: World) -> Pair:
    return Pair(client, world)


def report(
    pair: Pair, headers: dict[str, str], reason: str = "spam", note: str | None = None
) -> Any:
    return pair.client.post(
        f"{API}/chat/conversations/{pair.id}/report",
        json={"reason": reason, **({"note": note} if note else {})},
        headers=headers,
    )


def headers_for(client: TestClient, person: Person) -> dict[str, str]:
    """Log in an existing person (the OWNER, a church ADMIN) with a fresh password."""
    password = secrets.token_urlsafe(16)
    person.password_hash = hash_password(password)
    return headers_of(client, Member(person, password))


def owner_headers(client: TestClient, world: World) -> dict[str, str]:
    return headers_for(client, world.owner)


# ---- reporting ----------------------------------------------------------------------------------


def test_either_side_can_report_and_a_second_report_changes_nothing(pair: Pair) -> None:
    first = report(pair, pair.p, "harassment", "  rude  ")
    again = report(pair, pair.p, "spam")
    other_side = report(pair, pair.s, "scam")
    assert (first.status_code, again.status_code, other_side.status_code) == (201, 200, 201)
    assert first.json()["id"] == again.json()["id"] and first.json()["reason"] == "harassment"
    rows = pair.world.session.scalars(select(ChatReport)).all()
    assert len(rows) == 2
    mine = next(r for r in rows if r.reported_by_side == "provider")
    assert mine.note == "rude" and mine.reporter_id == pair.provider.person.id


@pytest.mark.parametrize(
    "body", [{"reason": "nonsense"}, {}, {"reason": "spam", "note": "x" * 501}]
)
def test_a_report_needs_a_known_reason_and_a_short_note(pair: Pair, body: dict[str, Any]) -> None:
    response = pair.client.post(
        f"{API}/chat/conversations/{pair.id}/report", json=body, headers=pair.p
    )
    assert response.status_code == 422


def test_only_a_participant_can_report(pair: Pair, client: TestClient, world: World) -> None:
    stranger = headers_of(client, add_member(world, "provider"))
    assert report(pair, stranger).status_code == 404


def test_a_handled_report_can_be_followed_by_a_new_one(
    pair: Pair, client: TestClient, world: World
) -> None:
    first = report(pair, pair.p).json()["id"]
    owner = owner_headers(client, world)
    assert client.post(f"{API}/owner/chat-reports/{first}/handle", headers=owner).status_code == 204
    second = report(pair, pair.p)
    assert second.status_code == 201 and second.json()["id"] != first


# ---- the OWNER ----------------------------------------------------------------------


def test_the_owner_lists_reports_without_any_message_text(
    pair: Pair, client: TestClient, world: World
) -> None:
    pair.send(pair.s, "do not show this text in the list")
    report(pair, pair.p, "scam", "asked for money")
    owner = owner_headers(client, world)
    listing = client.get(f"{API}/owner/chat-reports", headers=owner).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["reason"] == "scam" and item["note"] == "asked for money"
    assert item["reporter"]["full_name"] == pair.provider.person.full_name
    assert item["other"]["full_name"] == pair.starter.person.full_name
    assert "do not show" not in str(listing)
    open_only = client.get(f"{API}/owner/chat-reports", params={"handled": "false"}, headers=owner)
    handled_only = client.get(
        f"{API}/owner/chat-reports", params={"handled": "true"}, headers=owner
    )
    assert (open_only.json()["total"], handled_only.json()["total"]) == (1, 0)


def test_reading_a_reported_conversation_is_logged_each_time(
    pair: Pair, client: TestClient, world: World
) -> None:
    pair.send(pair.s, "first")
    pair.send(pair.p, "second")
    report_id = report(pair, pair.p).json()["id"]
    owner = owner_headers(client, world)
    url = f"{API}/owner/chat-reports/{report_id}/messages"
    first = client.get(url, headers=owner)
    client.get(url, headers=owner)
    assert [m["body"] for m in first.json()] == ["first", "second"]  # oldest first
    assert first.json()[1]["sender_side"] == "provider"
    assert first.json()[0]["sender_name"] == pair.starter.person.full_name
    views = world.session.scalars(select(ChatReportView)).all()
    assert len(views) == 2 and {v.viewer_id for v in views} == {world.owner.id}
    assert not hasattr(views[0], "body")  # who and when, never what


def test_an_unreported_conversation_cannot_be_read_by_anyone_else(
    pair: Pair, client: TestClient, world: World
) -> None:
    pair.send(pair.s, "private")
    owner = owner_headers(client, world)
    unknown = client.get(f"{API}/owner/chat-reports/{uuid.uuid4()}/messages", headers=owner)
    assert unknown.status_code == 404
    # The conversation id is not a way in: only a report id is.
    assert (
        client.get(f"{API}/owner/chat-reports/{pair.id}/messages", headers=owner).status_code == 404
    )


@pytest.mark.parametrize("status", ["searcher", "provider", "verifier", "admin"])
def test_only_the_owner_reads_reports(
    pair: Pair, client: TestClient, world: World, status: str
) -> None:
    report_id = report(pair, pair.p).json()["id"]
    if status == "admin":
        headers = headers_for(client, world.add_church("Another church")[2])
    else:
        headers = headers_of(client, add_member(world, status))
    for method, path in (
        ("GET", "/owner/chat-reports"),
        ("GET", f"/owner/chat-reports/{report_id}/messages"),
        ("POST", f"/owner/chat-reports/{report_id}/handle"),
    ):
        response = client.request(method, f"{API}{path}", headers=headers)
        assert response.status_code == 403, (status, path)
    assert world.session.scalar(select(func.count()).select_from(ChatReportView)) == 0


def test_handling_a_report_marks_it_and_is_repeatable(
    pair: Pair, client: TestClient, world: World
) -> None:
    report_id = report(pair, pair.s).json()["id"]
    owner = owner_headers(client, world)
    url = f"{API}/owner/chat-reports/{report_id}/handle"
    assert client.post(url, headers=owner).status_code == 204
    assert client.post(url, headers=owner).status_code == 204
    row = world.session.get(ChatReport, uuid.UUID(report_id))
    assert row is not None and row.handled_by_id == world.owner.id and row.handled_at is not None
    assert (
        code(client.get(f"{API}/owner/chat-reports/{uuid.uuid4()}/messages", headers=owner))
        == "not_found"
    )


# ---- the report RP-10 ----------------------------------------------------------------------------


def test_rp10_counts_reports_by_reason_and_week_without_names_or_text(
    pair: Pair, client: TestClient, world: World
) -> None:
    pair.send(pair.s, "text that must not appear")
    first = report(pair, pair.p, "spam", "a private note").json()["id"]
    report(pair, pair.s, "scam")
    owner = owner_headers(client, world)
    client.post(f"{API}/owner/chat-reports/{first}/handle", headers=owner)
    today = date.today()
    result = build_report(
        world.session, "chat_reports", params(today.replace(day=1), date(today.year + 1, 1, 1))
    )
    summary, by_reason, by_week = result.sections
    assert summary.rows == [[2, 1, 1]]
    assert by_reason.rows == [["scam", 1, 1, 0], ["spam", 1, 0, 1]]
    assert sum(row[1] for row in by_week.rows) == 2
    everything = str(result.sections)
    for private in (
        "text that must not appear",
        "a private note",
        str(pair.starter.person.full_name),
        str(pair.id),
    ):
        assert private not in everything
