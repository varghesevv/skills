"""Push for chat (S8.5): device addresses, the outbox, the cancel rule and the Firebase sender."""

import json
import uuid
from collections.abc import Iterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.chat import push
from app.core.config import Settings, get_settings
from app.main import app
from app.models.chat import ConversationState, DeviceToken, PushOutbox
from app.services.account_closing import clear_account
from tests.api_helpers import API
from tests.test_chat_api import Pair
from tests.trust_helpers import World

pytestmark = pytest.mark.db

URI_FIELD = "token_uri"  # the name Google gives it in a key file
AUTH_URL = "https://auth.example/oauth"
LATER = datetime.now(UTC) + timedelta(hours=1)


class FakeSender:
    def __init__(self, answer: push.Result = "ok") -> None:
        self.answer: push.Result = answer
        self.sent: list[tuple[str, str, str, dict[str, str]]] = []

    def send(self, address: str, title: str, body: str, data: dict[str, str]) -> push.Result:
        self.sent.append((address, title, body, data))
        return self.answer


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture
def pair(client: TestClient, world: World) -> Iterator[Pair]:
    """A pair with push switched on for the API."""
    base = get_settings()
    app.dependency_overrides[get_settings] = lambda: base.model_copy(update={"push_enabled": True})
    yield Pair(client, world)


def factory(session: Session) -> Any:
    return lambda: nullcontext(session)


def register(pair: Pair, headers: dict[str, str], address: str = "address-one") -> Any:
    return pair.client.post(f"{API}/chat/devices", json={"token": address}, headers=headers)


def rows(session: Session) -> list[PushOutbox]:
    return list(session.scalars(select(PushOutbox)).all())


# ---- device addresses --------------------------------------------------------------


def test_a_device_is_registered_once_and_forgotten_on_request(pair: Pair) -> None:
    first = register(pair, pair.p)
    again = register(pair, pair.p)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    url = f"{API}/chat/devices/{first.json()['id']}"
    assert pair.client.delete(url, headers=pair.s).status_code == 404  # not theirs
    assert pair.client.delete(url, headers=pair.p).status_code == 204
    assert pair.client.delete(url, headers=pair.p).status_code == 404


def test_an_address_moves_to_the_person_who_registers_it_now(pair: Pair) -> None:
    register(pair, pair.p, "shared-phone")
    register(pair, pair.s, "shared-phone")
    owner = pair.world.session.scalar(select(DeviceToken.person_id))
    assert owner == pair.starter.person.id
    assert pair.world.session.scalar(select(func.count()).select_from(DeviceToken)) == 1


def test_the_oldest_devices_beyond_the_limit_are_forgotten(pair: Pair) -> None:
    limit = get_settings().chat_max_devices_per_person
    for number in range(limit + 2):
        assert register(pair, pair.p, f"phone-{number}").status_code == 201
        pair.world.session.execute(  # the test transaction has one clock: set the times
            update(DeviceToken)
            .where(DeviceToken.token == f"phone-{number}")
            .values(last_seen_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=number))
        )
    kept = pair.world.session.scalars(
        select(DeviceToken.token).where(DeviceToken.person_id == pair.provider.person.id)
    ).all()
    assert len(kept) == limit and f"phone-{limit + 1}" in kept and "phone-0" not in kept


@pytest.mark.parametrize(
    "body", [{}, {"token": ""}, {"token": "x" * 513}, {"token": "a", "platform": "ios"}]
)
def test_a_device_needs_an_address_and_a_known_platform(pair: Pair, body: dict[str, Any]) -> None:
    assert pair.client.post(f"{API}/chat/devices", json=body, headers=pair.p).status_code == 422


def test_closing_an_account_forgets_its_devices_and_pending_pushes(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "hello")
    assert len(rows(pair.world.session)) == 1
    clear_account(pair.world.session, pair.provider.person, datetime.now(UTC))
    assert pair.world.session.scalar(select(func.count()).select_from(DeviceToken)) == 0
    assert rows(pair.world.session) == []


# ---- the outbox --------------------------------------------------------------------


def test_a_message_waits_in_the_outbox_and_a_burst_is_one_row(pair: Pair) -> None:
    register(pair, pair.p)
    for number in range(3):
        pair.send(pair.s, f"m{number}")
    (row,) = rows(pair.world.session)
    assert (row.message_count, row.state, row.side) == (3, "pending", "provider")
    assert row.person_id == pair.provider.person.id and row.last_seq > 0


@pytest.mark.parametrize("case", ["no device", "muted", "off"])
def test_no_row_is_made_when_nothing_would_be_sent(pair: Pair, case: str) -> None:
    if case != "no device":
        register(pair, pair.p)
    if case == "muted":
        pair.client.put(
            f"{API}/chat/conversations/{pair.id}/settings", json={"muted": True}, headers=pair.p
        )
    if case == "off":
        app.dependency_overrides.pop(get_settings)
    pair.send(pair.s, "hello")
    assert rows(pair.world.session) == []


def test_the_sender_s_own_devices_get_nothing(pair: Pair) -> None:
    register(pair, pair.s)
    pair.send(pair.s, "hello")
    assert rows(pair.world.session) == []


# ---- sending and cancelling --------------------------------------------------------


def test_a_due_row_sends_one_generic_push_without_the_text(pair: Pair) -> None:
    register(pair, pair.p, "the-phone")
    pair.send(pair.s, "a private sentence")
    sender = FakeSender()
    session = pair.world.session
    assert push.process_due(factory(session), sender, now=datetime.now(UTC)) == {}  # not yet due
    assert push.process_due(factory(session), sender, now=LATER) == {"sent": 1}
    (address, title, body, data) = sender.sent[0]
    assert address == "the-phone" and (title, body) == (push.TITLE, push.BODY_ONE)
    assert data == {"type": "chat", "conversation_id": pair.id}
    assert "private" not in json.dumps(sender.sent)
    assert rows(session)[0].state == "sent"
    assert push.process_due(factory(session), sender, now=LATER) == {}  # once only


def test_several_messages_make_one_push_with_the_plural_text(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "one")
    pair.send(pair.s, "two")
    sender = FakeSender()
    push.process_due(factory(pair.world.session), sender, now=LATER)
    assert [s[2] for s in sender.sent] == [push.BODY_MANY]


def test_a_message_already_delivered_or_read_is_not_pushed(pair: Pair) -> None:
    register(pair, pair.p)
    session = pair.world.session
    sent = pair.send(pair.s, "hello").json()
    rules_state = session.get(ConversationState, (uuid.UUID(pair.id), "provider"))
    assert rules_state is not None
    rules_state.delivered_seq = sent["seq"]
    session.flush()
    sender = FakeSender()
    assert push.process_due(factory(session), sender, now=LATER) == {"delivered": 1}
    assert sender.sent == []
    # A later message starts a new row, and a read mark cancels it as well.
    later = pair.send(pair.s, "again").json()
    rules_state.last_read_seq = later["seq"]
    session.flush()
    assert push.process_due(factory(session), sender, now=LATER) == {"delivered": 1}
    assert sender.sent == []


def test_a_closed_blocked_or_muted_person_is_not_pushed(pair: Pair) -> None:
    register(pair, pair.p)
    session = pair.world.session
    pair.send(pair.s, "hello")
    state = session.get(ConversationState, (uuid.UUID(pair.id), "provider"))
    assert state is not None
    state.muted = True  # muted after the row was made
    session.flush()
    sender = FakeSender()
    assert push.process_due(factory(session), sender, now=LATER) == {"muted": 1}
    state.muted = False
    state.blocked = True
    session.flush()
    session.add(
        PushOutbox(
            person_id=pair.provider.person.id,
            conversation_id=uuid.UUID(pair.id),
            side="provider",
            last_seq=10**9,
            send_after=LATER - timedelta(minutes=2),
        )
    )
    session.flush()
    assert push.process_due(factory(session), sender, now=LATER) == {"blocked": 1}
    state.blocked = False
    clear_account(session, pair.provider.person, datetime.now(UTC))
    session.flush()
    row = PushOutbox(
        person_id=pair.provider.person.id,
        conversation_id=uuid.UUID(pair.id),
        side="provider",
        last_seq=10**9,
        send_after=LATER - timedelta(minutes=1),
    )
    session.add(row)
    session.flush()
    assert push.process_due(factory(session), sender, now=LATER) == {"closed": 1}
    assert sender.sent == []


def test_an_address_the_phone_gave_up_is_forgotten(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "hello")
    session = pair.world.session
    result = push.process_due(factory(session), FakeSender("invalid"), now=LATER)
    assert result == {"no_device": 1}
    assert session.scalar(select(func.count()).select_from(DeviceToken)) == 0


def test_a_failed_send_is_tried_again_and_given_up_after_five_times(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "hello")
    session = pair.world.session
    sender = FakeSender("retry")
    moment = LATER
    for attempt in range(1, push.MAX_ATTEMPTS):
        assert push.process_due(factory(session), sender, now=moment) == {"retry": 1}
        row = rows(session)[0]
        assert (row.state, row.attempts) == ("pending", attempt)
        moment = row.send_after + timedelta(seconds=1)
    assert push.process_due(factory(session), sender, now=moment) == {"failed": 1}
    assert (rows(session)[0].state, rows(session)[0].reason) == ("cancelled", "failed")


def test_a_message_that_arrives_while_sending_still_gets_its_own_push(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "first")
    session = pair.world.session

    class Busy(FakeSender):
        def send(self, address: str, title: str, body: str, data: dict[str, str]) -> push.Result:
            if not self.sent:
                pair.send(pair.s, "second")  # arrives while Firebase is being called
            return super().send(address, title, body, data)

    sender = Busy()
    assert push.process_due(factory(session), sender, now=LATER)
    assert [row.state for row in rows(session)] == ["pending"]
    assert push.process_due(factory(session), sender, now=LATER + timedelta(minutes=5)) == {
        "sent": 1
    }
    assert len(sender.sent) == 2 and rows(session)[0].state == "sent"


def test_a_row_being_sent_is_not_picked_up_again_at_once(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "hello")
    session = pair.world.session
    claimed = push._claim(factory(session), LATER)
    assert len(claimed) == 1 and push._claim(factory(session), LATER) == []


def test_a_moved_address_is_pruned_like_a_new_one(pair: Pair) -> None:
    limit = get_settings().chat_max_devices_per_person
    for number in range(limit):
        register(pair, pair.p, f"own-{number}")
    register(pair, pair.s, "other-phone")
    register(pair, pair.p, "other-phone")  # moves to the provider, who is at the limit
    count = pair.world.session.scalar(
        select(func.count())
        .select_from(DeviceToken)
        .where(DeviceToken.person_id == pair.provider.person.id)
    )
    assert count == limit


def test_old_finished_rows_are_deleted_and_pending_ones_kept(pair: Pair) -> None:
    register(pair, pair.p)
    pair.send(pair.s, "hello")
    session = pair.world.session
    settings = get_settings()
    push.process_due(factory(session), FakeSender(), now=LATER)
    pair.send(pair.p, "answer")  # a pending row for the starter
    assert push.purge_finished(session, settings, now=LATER) == 0
    far = LATER + timedelta(days=settings.chat_push_keep_days + 1)
    # "Finished" is stamped with the moment given above, so the purge is measured from there.
    assert push.purge_finished(session, settings, now=far + timedelta(days=1)) == 1


# ---- Firebase ------------------------------------------------------------------------------------


def key_file() -> tuple[str, Any]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    body = {
        "project_id": "demo-project",
        "client_email": "sender@demo-project.example",
        "private_key": pem,
        URI_FIELD: AUTH_URL,
    }
    return json.dumps(body), key.public_key()


def sender_with(answers: list[httpx.Response], seen: list[httpx.Request]) -> push.FcmSender:
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "auth.example":
            return httpx.Response(200, json={"access_token": "a" * 40, "expires_in": 3600})
        return queue.pop(0)

    text, _ = key_file()
    return push.FcmSender(text, client=httpx.Client(transport=httpx.MockTransport(handle)))


def test_the_firebase_sender_signs_the_request_and_sends_the_message() -> None:
    seen: list[httpx.Request] = []
    sender = sender_with([httpx.Response(200, json={}), httpx.Response(200, json={})], seen)
    assert sender.send("phone", "T", "B", {"type": "chat"}) == "ok"
    assert sender.send("phone", "T", "B", {"type": "chat"}) == "ok"
    auth = [r for r in seen if r.url.host == "auth.example"]
    assert len(auth) == 1  # the access key is reused
    assertion = dict(x.split("=") for x in auth[0].content.decode().split("&"))["assertion"]
    claims = jwt.decode(assertion, options={"verify_signature": False})
    assert (
        claims["iss"] == "sender@demo-project.example" and "firebase.messaging" in claims["scope"]
    )
    message = json.loads(seen[-1].content)["message"]
    assert message["token"] == "phone" and message["data"] == {"type": "chat"}
    assert seen[-1].url.path == "/v1/projects/demo-project/messages:send"
    assert seen[-1].headers["authorization"] == "Bearer " + "a" * 40


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(404, json={}), "retry"),  # a wrong project must not delete addresses
        (
            httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}}),
            "invalid",
        ),
        (
            httpx.Response(400, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}}),
            "invalid",
        ),
        (httpx.Response(400, json={"error": {"details": []}}), "retry"),
        (httpx.Response(503, json={}), "retry"),
        (httpx.Response(429, json={}), "retry"),
    ],
)
def test_the_firebase_answers_are_told_apart(response: httpx.Response, expected: str) -> None:
    assert sender_with([response], []).send("phone", "T", "B", {}) == expected


def test_an_expired_access_key_is_renewed_once() -> None:
    seen: list[httpx.Request] = []
    sender = sender_with([httpx.Response(401, json={}), httpx.Response(200, json={})], seen)
    assert sender.send("phone", "T", "B", {}) == "ok"
    assert len([r for r in seen if r.url.host == "auth.example"]) == 2


def test_a_key_that_cannot_sign_stops_the_worker_at_start() -> None:
    text = json.dumps({"project_id": "p", "client_email": "e@x.example", "private_key": "nonsense"})
    settings = Settings.model_construct(push_enabled=True, fcm_service_account_json=SecretStr(text))
    with pytest.raises(RuntimeError, match="usable"):
        push.build_sender(settings)


def test_a_missing_key_stops_the_worker_at_start() -> None:
    settings = Settings.model_construct(push_enabled=True, fcm_service_account_json=None)
    with pytest.raises(RuntimeError, match="FCM_SERVICE_ACCOUNT_JSON"):
        push.build_sender(settings)
