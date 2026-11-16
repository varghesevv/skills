"""Chat over REST (S8.2): who may write to whom, idempotent sending, limits, blocking, unread."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.chat import rules
from app.models.chat import ConversationState
from app.services.account_closing import clear_account
from tests.api_helpers import API
from tests.test_admission import headers_of
from tests.test_person_auth import add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


class Pair:
    def __init__(self, client: TestClient, world: World) -> None:
        self.client = client
        self.world = world
        self.starter = add_member(world, "searcher")
        self.provider = add_member(world, "provider")
        self.s = headers_of(client, self.starter)
        self.p = headers_of(client, self.provider)
        response = client.post(
            f"{API}/chat/conversations",
            json={"provider_id": str(self.provider.person.id)},
            headers=self.s,
        )
        assert response.status_code == 201, response.text
        self.id = response.json()["id"]

    def send(self, headers: dict[str, str], body: str = "Hello", cid: str | None = None) -> Any:
        return self.client.post(
            f"{API}/chat/conversations/{self.id}/messages",
            json={"client_message_id": cid or str(uuid.uuid4()), "body": body},
            headers=headers,
        )


@pytest.fixture
def pair(client: TestClient, world: World) -> Pair:
    return Pair(client, world)


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


# ---- starting --------------------------------------------------------------------------------


def test_a_searcher_starts_a_conversation_with_a_provider_once(
    client: TestClient, world: World
) -> None:
    starter, provider = add_member(world, "searcher"), add_member(world, "provider")
    headers = headers_of(client, starter)
    body = {"provider_id": str(provider.person.id)}
    first = client.post(f"{API}/chat/conversations", json=body, headers=headers)
    again = client.post(f"{API}/chat/conversations", json=body, headers=headers)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["my_side"] == "starter"
    assert first.json()["other"]["full_name"] == provider.person.full_name


def test_one_conversation_can_be_read_by_its_id_whatever_the_page_of_the_list(
    pair: Pair,
) -> None:
    pair.send(pair.s, "hi")
    mine = pair.client.get(f"{API}/chat/conversations/{pair.id}", headers=pair.s).json()
    theirs = pair.client.get(f"{API}/chat/conversations/{pair.id}", headers=pair.p).json()
    assert (mine["id"], mine["my_side"], mine["unread_count"]) == (pair.id, "starter", 0)
    assert (theirs["my_side"], theirs["unread_count"]) == ("provider", 1)
    assert theirs["other"]["full_name"] == pair.starter.person.full_name


def test_a_provider_appears_in_the_list_of_the_provider_too(pair: Pair) -> None:
    listing = pair.client.get(f"{API}/chat/conversations", headers=pair.p).json()
    assert listing["total"] == 1
    assert listing["items"][0]["my_side"] == "provider"
    assert listing["items"][0]["other"]["full_name"] == pair.starter.person.full_name


@pytest.mark.parametrize("status", ["searcher", "pending", "revoked"])
def test_only_a_provider_or_above_can_be_written_to_and_only_by_the_admitted(
    client: TestClient, world: World, status: str
) -> None:
    starter = add_member(world, "searcher")
    target = add_member(world, status)
    response = client.post(
        f"{API}/chat/conversations",
        json={"provider_id": str(target.person.id)},
        headers=headers_of(client, starter),
    )
    assert response.status_code == 404  # looks like nobody


@pytest.mark.parametrize("status", ["pending", "revoked"])
def test_an_applicant_or_a_revoked_person_cannot_start_one(
    client: TestClient, world: World, status: str
) -> None:
    provider = add_member(world, "provider")
    person = add_member(world, status)
    response = client.post(
        f"{API}/chat/conversations",
        json={"provider_id": str(provider.person.id)},
        headers=headers_of(client, person),
    )
    assert response.status_code == 403


def test_nobody_writes_to_themselves(client: TestClient, world: World) -> None:
    provider = add_member(world, "provider")
    response = client.post(
        f"{API}/chat/conversations",
        json={"provider_id": str(provider.person.id)},
        headers=headers_of(client, provider),
    )
    assert (response.status_code, code(response)) == (422, "cannot_message_self")


def test_the_number_of_new_conversations_per_day_is_limited(
    client: TestClient, world: World
) -> None:
    starter = add_member(world, "searcher")
    headers = headers_of(client, starter)  # the test limit is 3
    results = [
        client.post(
            f"{API}/chat/conversations",
            json={"provider_id": str(add_member(world, "provider").person.id)},
            headers=headers,
        )
        for _ in range(4)
    ]
    assert [r.status_code for r in results] == [201, 201, 201, 429]
    assert code(results[3]) == "chat_new_conversation_limit"


def test_one_conversation_per_pair_of_people_whoever_writes_first(
    client: TestClient, world: World
) -> None:
    first, second = add_member(world, "provider"), add_member(world, "provider")
    a, b = headers_of(client, first), headers_of(client, second)
    one = client.post(
        f"{API}/chat/conversations", json={"provider_id": str(second.person.id)}, headers=a
    )
    back = client.post(
        f"{API}/chat/conversations", json={"provider_id": str(first.person.id)}, headers=b
    )
    assert (one.status_code, back.status_code) == (201, 200)
    assert one.json()["id"] == back.json()["id"]
    assert back.json()["my_side"] == "provider"  # the second one answers in the first one's thread


# ---- sending ---------------------------------------------------------------------------------


def test_both_sides_exchange_messages_and_see_them_newest_first(pair: Pair) -> None:
    assert pair.send(pair.s, "Hello").status_code == 201
    reply = pair.send(pair.p, "Hi, yes")
    assert reply.status_code == 201 and reply.json()["sender_side"] == "provider"
    pair.send(pair.s, "Great")
    history = pair.client.get(f"{API}/chat/conversations/{pair.id}/messages", headers=pair.p).json()
    assert [m["body"] for m in history] == ["Great", "Hi, yes", "Hello"]
    assert [m["seq"] for m in history] == sorted((m["seq"] for m in history), reverse=True)


def test_a_retry_with_the_same_id_stores_the_message_once(pair: Pair) -> None:
    cid = str(uuid.uuid4())
    first, retry = pair.send(pair.s, "Once", cid), pair.send(pair.s, "Once", cid)
    assert (first.status_code, retry.status_code) == (201, 200)
    assert first.json()["id"] == retry.json()["id"]
    history = pair.client.get(f"{API}/chat/conversations/{pair.id}/messages", headers=pair.s).json()
    assert len(history) == 1


def test_the_cursor_pages_through_history(pair: Pair) -> None:
    for n in range(3):
        pair.send(pair.p if n % 2 else pair.s, f"m{n}")
        pair.client.get(f"{API}/chat/unread", headers=pair.s)  # keeps the minute count small
    url = f"{API}/chat/conversations/{pair.id}/messages"
    first = pair.client.get(url, params={"limit": 2}, headers=pair.s).json()
    assert [m["body"] for m in first] == ["m2", "m1"]
    rest = pair.client.get(
        url, params={"limit": 2, "before_seq": first[-1]["seq"]}, headers=pair.s
    ).json()
    assert [m["body"] for m in rest] == ["m0"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", "chat_message_empty"),
        ("   \n ", "chat_message_empty"),
        ("x" * 2001, "chat_message_too_long"),
        ("bad\x00text", "chat_message_invalid"),
    ],
)
def test_a_message_must_be_text_of_the_right_length(pair: Pair, body: str, expected: str) -> None:
    response = pair.send(pair.s, body)
    assert (response.status_code, code(response)) == (422, expected)


def test_a_message_is_trimmed_and_may_have_new_lines(pair: Pair) -> None:
    response = pair.send(pair.s, "  two\nlines  ")
    assert response.json()["body"] == "two\nlines"


def test_a_sender_is_locked_before_the_limit_is_counted(
    pair: Pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parallel sends of one person are stored one at a time, so the limit cannot be passed."""
    order: list[str] = []
    real_lock, real_count = rules.lock_people, rules._sent_in_last_minute

    def lock(db: Session, ids: Any) -> Any:
        order.append("lock")
        return real_lock(db, ids)

    def count(db: Session, person_id: uuid.UUID) -> int:
        order.append("count")
        return real_count(db, person_id)

    monkeypatch.setattr(rules, "lock_people", lock)
    monkeypatch.setattr(rules, "_sent_in_last_minute", count)
    assert pair.send(pair.s, "hi").status_code == 201
    assert order == ["lock", "count"]


def test_messages_per_minute_are_limited(pair: Pair) -> None:
    results = [pair.send(pair.s, f"m{n}") for n in range(6)]  # the test limit is 5
    assert [r.status_code for r in results] == [201] * 5 + [429]
    assert code(results[5]) == "chat_rate_limited"


def test_someone_outside_the_conversation_finds_nothing(
    pair: Pair, client: TestClient, world: World
) -> None:
    stranger = headers_of(client, add_member(world, "provider"))
    pair.send(pair.s, "private")
    url = f"{API}/chat/conversations/{pair.id}"
    assert client.get(f"{url}/messages", headers=stranger).status_code == 404
    assert pair.send(stranger).status_code == 404
    assert client.post(f"{url}/read", json={"up_to_seq": 1}, headers=stranger).status_code == 404
    assert client.put(f"{url}/settings", json={"muted": True}, headers=stranger).status_code == 404
    unknown = client.get(f"{API}/chat/conversations/{uuid.uuid4()}/messages", headers=stranger)
    assert unknown.status_code == 404
    assert client.get(url, headers=stranger).status_code == 404
    assert (
        client.get(f"{API}/chat/conversations/{uuid.uuid4()}", headers=stranger).status_code == 404
    )


def test_nothing_is_stored_for_a_person_who_has_closed_their_account(pair: Pair) -> None:
    clear_account(pair.world.session, pair.provider.person, datetime.now(UTC))
    pair.world.session.flush()
    response = pair.send(pair.s, "Anyone there?")
    assert (response.status_code, code(response)) == (409, "chat_closed")
    other = pair.client.get(f"{API}/chat/conversations", headers=pair.s).json()["items"][0]["other"]
    assert other["closed"] is True and other["full_name"] is None


# ---- read marks and unread -------------------------------------------------------------------


def test_unread_counts_follow_the_read_marks(pair: Pair) -> None:
    for word in ("a", "b", "c"):
        pair.send(pair.s, word)
    unread = lambda h: pair.client.get(f"{API}/chat/unread", headers=h).json()["total"]  # noqa: E731
    assert (unread(pair.s), unread(pair.p)) == (0, 3)  # the sender has read their own
    listing = pair.client.get(f"{API}/chat/conversations", headers=pair.p).json()["items"][0]
    assert listing["unread_count"] == 3 and listing["last_message_preview"] == "c"
    history = pair.client.get(f"{API}/chat/conversations/{pair.id}/messages", headers=pair.p).json()
    middle = history[1]["seq"]
    url = f"{API}/chat/conversations/{pair.id}/read"
    assert pair.client.post(url, json={"up_to_seq": middle}, headers=pair.p).status_code == 204
    assert unread(pair.p) == 1
    pair.client.post(url, json={"up_to_seq": 1}, headers=pair.p)  # never backwards
    assert unread(pair.p) == 1
    pair.client.post(url, json={"up_to_seq": 10**12}, headers=pair.p)  # nor beyond the newest
    assert unread(pair.p) == 0


def test_a_late_read_mark_never_moves_the_mark_back(pair: Pair) -> None:
    """Sending moves the sender's own mark to the new message; an older read mark that arrives
    afterwards (another device, a slow request) must not lower it."""
    pair.send(pair.s, "one")
    last = pair.send(pair.s, "two").json()["seq"]
    url = f"{API}/chat/conversations/{pair.id}/read"
    assert pair.client.post(url, json={"up_to_seq": 1}, headers=pair.s).status_code == 204
    assert pair.client.get(f"{API}/chat/unread", headers=pair.s).json()["total"] == 0
    state = pair.world.session.get(ConversationState, (uuid.UUID(pair.id), "starter"))
    assert state is not None and state.last_read_seq == last and state.delivered_seq == last


def test_the_preview_is_short(pair: Pair) -> None:
    pair.send(pair.s, "y" * 500)
    item = pair.client.get(f"{API}/chat/conversations", headers=pair.p).json()["items"][0]
    assert len(item["last_message_preview"]) == 60


def test_the_list_puts_the_latest_activity_first(client: TestClient, world: World) -> None:
    starter = add_member(world, "searcher")
    headers = headers_of(client, starter)
    ids = []
    for _ in range(2):
        provider = add_member(world, "provider")
        ids.append(
            client.post(
                f"{API}/chat/conversations",
                json={"provider_id": str(provider.person.id)},
                headers=headers,
            ).json()["id"]
        )
    # One transaction in a test, so now() is the same everywhere: make the second one older.
    world.session.execute(
        text("UPDATE conversations SET created_at = created_at - interval '1 day' WHERE id = :id"),
        {"id": ids[1]},
    )
    client.post(
        f"{API}/chat/conversations/{ids[0]}/messages",
        json={"client_message_id": str(uuid.uuid4()), "body": "bump"},
        headers=headers,
    )
    listing = client.get(f"{API}/chat/conversations", headers=headers).json()["items"]
    assert [i["id"] for i in listing] == [ids[0], ids[1]]


# ---- settings and blocking -------------------------------------------------------------------


def test_a_provider_can_mute_and_block_and_a_block_stops_both_ways(pair: Pair) -> None:
    pair.send(pair.s, "hi")
    url = f"{API}/chat/conversations/{pair.id}/settings"
    muted = pair.client.put(url, json={"muted": True}, headers=pair.p).json()
    assert muted["muted"] is True and muted["blocked"] is False
    assert pair.client.put(url, json={"blocked": True}, headers=pair.p).json()["blocked"] is True
    assert code(pair.send(pair.s, "again")) == "chat_blocked"
    assert code(pair.send(pair.p, "me too")) == "chat_blocked"
    start = pair.client.post(
        f"{API}/chat/conversations",
        json={"provider_id": str(pair.provider.person.id)},
        headers=pair.s,
    )
    assert (start.status_code, code(start)) == (403, "chat_blocked")
    pair.client.put(url, json={"blocked": False}, headers=pair.p)
    assert pair.send(pair.s, "back").status_code == 201


def test_the_starter_cannot_block_and_is_not_told_about_a_block(pair: Pair) -> None:
    url = f"{API}/chat/conversations/{pair.id}/settings"
    refused = pair.client.put(url, json={"blocked": True}, headers=pair.s)
    assert (refused.status_code, code(refused)) == (403, "chat_not_allowed")
    pair.client.put(url, json={"blocked": True}, headers=pair.p)
    listing = pair.client.get(f"{API}/chat/conversations", headers=pair.s).json()["items"][0]
    assert listing["blocked"] is False  # the starter's list never says


# ---- events ----------------------------------------------------------------------------------


def test_storing_a_message_announces_ids_only_to_the_recipient_and_the_senders_devices(
    pair: Pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(rules, "notify", lambda db, event: events.append(event))
    sent = pair.send(pair.s, "secret text").json()
    assert len(events) == 1
    event = events[0]
    assert event["kind"] == "message" and event["seq"] == sent["seq"]
    assert event["people"] == [str(pair.provider.person.id), str(pair.starter.person.id)]
    assert "secret text" not in str(event)
    events.clear()
    pair.send(pair.s, "again", cid=sent and str(uuid.uuid4()))
    pair.send(pair.s, "dup", cid="00000000-0000-4000-8000-000000000001")
    events.clear()
    pair.send(pair.s, "dup", cid="00000000-0000-4000-8000-000000000001")
    assert events == []  # a retry announces nothing


def test_every_chat_endpoint_needs_a_token(client: TestClient) -> None:
    ghost = uuid.uuid4()
    for method, path in (
        ("GET", "/chat/conversations"),
        ("POST", "/chat/conversations"),
        ("GET", f"/chat/conversations/{ghost}/messages"),
        ("POST", f"/chat/conversations/{ghost}/messages"),
        ("POST", f"/chat/conversations/{ghost}/read"),
        ("PUT", f"/chat/conversations/{ghost}/settings"),
        ("GET", "/chat/unread"),
    ):
        assert client.request(method, f"{API}{path}").status_code == 401, (method, path)
