"""The chat WebSocket (S8.3): authentication, frames, limits, and ending a socket whose person may
no longer chat. Events that PostgreSQL would carry are routed straight into the runtime here
(the test transaction never commits); the carrying itself is tested in test_chat_hub.py."""

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.chat import rules, ws
from app.core.config import get_settings
from app.core.security import Principal, create_access_token
from app.models.chat import ConversationState
from tests.api_helpers import API
from tests.test_admission import headers_of
from tests.test_person_auth import add_member, login
from tests.trust_helpers import World

pytestmark = pytest.mark.db

URL = f"{API}/chat/ws"


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


@pytest.fixture
def runtime(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> Any:
    chat = client.app.state.chat  # type: ignore[attr-defined]
    chat.factory = lambda: _Same(session)

    def notify(db: Session, event: dict[str, Any]) -> None:
        assert chat.loop is not None
        asyncio.run_coroutine_threadsafe(chat.dispatch(event), chat.loop).result(timeout=10)

    monkeypatch.setattr(rules, "notify", notify)
    return chat


class _Same:
    """`with factory() as db` gives the test session and leaves it open."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, *args: object) -> None:
        return None


def token_of(client: TestClient, member: Any) -> str:
    return str(login(client, member)["access_token"])


_OPEN: list[Any] = []


@pytest.fixture(autouse=True)
def close_sockets(client: TestClient) -> Any:
    """Close every socket a test opened, before the client shuts down (it would wait for them)."""
    yield
    while _OPEN:
        context = _OPEN.pop()
        with contextlib.suppress(Exception):  # a socket the server already closed
            context.__exit__(None, None, None)


def connect(client: TestClient, token: str) -> Any:
    context = client.websocket_connect(URL)
    opened = context.__enter__()
    _OPEN.append(context)
    opened.send_json({"type": "auth", "token": token})
    return opened


def ready(client: TestClient, token: str) -> Any:
    opened = connect(client, token)
    assert opened.receive_json()["type"] == "ready"
    return opened


def new_message(cid: str | None = None, body: str = "Hello") -> dict[str, Any]:
    return {"client_message_id": cid or str(uuid.uuid4()), "body": body}


class Chat:
    def __init__(self, client: TestClient, world: World) -> None:
        self.client = client
        self.world = world
        self.starter = add_member(world, "searcher")
        self.provider = add_member(world, "provider")
        self.s_token = token_of(client, self.starter)
        self.p_token = token_of(client, self.provider)
        response = client.post(
            f"{API}/chat/conversations",
            json={"provider_id": str(self.provider.person.id)},
            headers={"Authorization": f"Bearer {self.s_token}"},
        )
        self.id = response.json()["id"]


@pytest.fixture
def chat(client: TestClient, world: World, runtime: Any) -> Chat:
    return Chat(client, world)


def closed_with(socket: Any) -> int:
    with pytest.raises(WebSocketDisconnect) as info:
        socket.receive_json()
    return int(info.value.code)


# ---- authentication --------------------------------------------------------------------------


def test_a_valid_token_opens_the_socket(client: TestClient, chat: Chat) -> None:
    with client.websocket_connect(URL) as socket:
        socket.send_json({"type": "auth", "token": chat.s_token})
        frame = socket.receive_json()
        assert frame["type"] == "ready" and frame["heartbeat_seconds"] == 25


@pytest.mark.parametrize(
    "first",
    [{"type": "auth", "token": "bad"}, {"type": "send"}, {"token": "x"}, ["list"]],
)
def test_anything_but_a_valid_auth_frame_is_refused(client: TestClient, first: Any) -> None:
    with client.websocket_connect(URL) as socket:
        socket.send_json(first)
        assert closed_with(socket) == 4401


def test_an_oversized_first_frame_is_refused_before_it_is_parsed(
    client: TestClient, runtime: Any
) -> None:
    with client.websocket_connect(URL) as socket:
        socket.send_text("{" + "x" * ws.MAX_FRAME_BYTES)
        assert closed_with(socket) == 1009


def test_a_binary_frame_closes_the_socket_cleanly_before_and_after_authentication(
    client: TestClient, chat: Chat
) -> None:
    with client.websocket_connect(URL) as before:
        before.send_bytes(b"\x00\x01")
        assert closed_with(before) == 4401
    after = ready(client, chat.s_token)
    after.send_bytes(b"\x00\x01")
    assert closed_with(after) == 1003


def test_a_socket_that_says_nothing_is_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, runtime: Any
) -> None:
    monkeypatch.setattr(ws, "AUTH_WAIT_SECONDS", 0.2)
    with client.websocket_connect(URL) as socket:
        assert closed_with(socket) == 4401


def test_an_applicant_has_no_chat(client: TestClient, world: World, runtime: Any) -> None:
    token = token_of(client, add_member(world, "pending"))
    with client.websocket_connect(URL) as socket:
        socket.send_json({"type": "auth", "token": token})
        assert closed_with(socket) == 4403


def test_the_token_is_never_read_from_the_address(client: TestClient, chat: Chat) -> None:
    with client.websocket_connect(f"{URL}?token={chat.s_token}") as socket:
        socket.send_json({"type": "ping"})  # a ping is not an auth frame
        assert closed_with(socket) == 4401


def test_an_expired_token_is_refused_and_a_short_one_ends_the_socket(
    client: TestClient, chat: Chat
) -> None:
    secret = get_settings().require_jwt_secret()
    old, _ = create_access_token(
        Principal(chat.starter.person.id),
        secret=secret,
        lifetime_minutes=15,
        now=datetime.now(UTC) - timedelta(hours=1),
    )
    with client.websocket_connect(URL) as socket:
        socket.send_json({"type": "auth", "token": old})
        assert closed_with(socket) == 4401
    nearly, _ = create_access_token(
        Principal(chat.starter.person.id),
        secret=secret,
        lifetime_minutes=15,
        now=datetime.now(UTC) - timedelta(minutes=15) + timedelta(seconds=1),
    )
    with client.websocket_connect(URL) as socket:
        socket.send_json({"type": "auth", "token": nearly})
        assert socket.receive_json()["type"] == "ready"
        assert closed_with(socket) == 4401  # the token ran out; the app refreshes and reconnects


# ---- frames ----------------------------------------------------------------------------------


def test_a_sent_message_is_acknowledged_and_reaches_both_people_and_the_senders_other_device(
    client: TestClient, chat: Chat
) -> None:
    sender = ready(client, chat.s_token)
    other_device = ready(client, chat.s_token)
    receiver = ready(client, chat.p_token)
    frame = {"type": "send", "conversation_id": chat.id, **new_message(body="Is Friday free?")}
    sender.send_json(frame)
    seen = [sender.receive_json(), sender.receive_json()]  # the ack and the event, either order
    assert {f["type"] for f in seen} == {"ack", "message"}
    ack = next(f for f in seen if f["type"] == "ack")
    assert ack["client_message_id"] == frame["client_message_id"]
    assert (
        ack["message"]["body"] == "Is Friday free?" and ack["message"]["sender_side"] == "starter"
    )
    for socket in (other_device, receiver):
        event = socket.receive_json()
        assert event["type"] == "message" and event["message"]["id"] == ack["message"]["id"]


def test_sending_the_same_message_again_returns_the_stored_one(
    client: TestClient, chat: Chat
) -> None:
    socket = ready(client, chat.s_token)
    frame = {"type": "send", "conversation_id": chat.id, **new_message()}
    ids = []
    for _ in range(2):
        socket.send_json(frame)
        got = [socket.receive_json() for _ in range(2 if not ids else 1)]
        ids.append(next(f for f in got if f["type"] == "ack")["message"]["id"])
    assert ids[0] == ids[1]


def test_a_refused_message_gets_an_error_frame_with_the_id_the_app_sent(
    client: TestClient, chat: Chat
) -> None:
    socket = ready(client, chat.s_token)
    cid = str(uuid.uuid4())
    socket.send_json(
        {"type": "send", "conversation_id": chat.id, "client_message_id": cid, "body": "x" * 2001}
    )
    assert socket.receive_json() == {
        "type": "error",
        "code": "chat_message_too_long",
        "client_message_id": cid,
    }


def test_someone_who_is_not_in_the_conversation_gets_not_found(
    client: TestClient, chat: Chat, world: World
) -> None:
    stranger = ready(client, token_of(client, add_member(world, "provider")))
    stranger.send_json({"type": "send", "conversation_id": chat.id, **new_message()})
    assert stranger.receive_json()["code"] == "not_found"


def test_a_read_mark_reaches_the_other_side_and_is_stored(
    client: TestClient, chat: Chat, session: Session
) -> None:
    starter, provider = ready(client, chat.s_token), ready(client, chat.p_token)
    starter.send_json({"type": "send", "conversation_id": chat.id, **new_message()})
    seq = next(f for f in (starter.receive_json(), starter.receive_json()) if f["type"] == "ack")[
        "message"
    ]["seq"]
    assert provider.receive_json()["type"] == "message"
    provider.send_json({"type": "delivered", "conversation_id": chat.id, "up_to_seq": seq})
    assert starter.receive_json() == {
        "type": "delivered",
        "conversation_id": chat.id,
        "side": "provider",
        "up_to_seq": seq,
    }
    provider.send_json({"type": "read", "conversation_id": chat.id, "up_to_seq": seq})
    assert starter.receive_json()["type"] == "read"
    state = session.get(ConversationState, (uuid.UUID(chat.id), "provider"))
    assert state is not None and state.last_read_seq == seq and state.delivered_seq == seq


def test_a_ping_is_answered_and_a_bad_frame_is_named(client: TestClient, chat: Chat) -> None:
    socket = ready(client, chat.s_token)
    socket.send_json({"type": "ping"})
    assert socket.receive_json() == {"type": "pong"}
    socket.send_text("not json")
    assert socket.receive_json() == {"type": "error", "code": "bad_frame"}
    socket.send_json({"type": "nonsense", "conversation_id": chat.id})
    assert socket.receive_json()["code"] == "bad_frame"
    socket.send_json({"type": "read", "conversation_id": chat.id, "up_to_seq": "7"})
    assert socket.receive_json()["code"] == "bad_frame"


# ---- limits and ending a socket --------------------------------------------------------------


def test_a_frame_that_is_too_large_closes_the_socket(client: TestClient, chat: Chat) -> None:
    socket = ready(client, chat.s_token)
    socket.send_text("x" * (ws.MAX_FRAME_BYTES + 1))
    assert closed_with(socket) == 1009


def test_a_flood_of_frames_closes_the_socket(
    client: TestClient, chat: Chat, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ws, "FRAMES_PER_WINDOW", 3)
    socket = ready(client, chat.s_token)
    for _ in range(4):
        socket.send_json({"type": "ping"})
    frames = 0
    with pytest.raises(WebSocketDisconnect) as info:
        for _ in range(5):
            socket.receive_json()
            frames += 1
    assert info.value.code == 4429 and frames == 3


def test_one_person_cannot_hold_too_many_sockets(
    client: TestClient, chat: Chat, runtime: Any
) -> None:
    runtime.hub._max = 2
    first, second = ready(client, chat.s_token), ready(client, chat.s_token)
    with client.websocket_connect(URL) as third:
        third.send_json({"type": "auth", "token": chat.s_token})
        assert closed_with(third) == 4429
    first.send_json({"type": "ping"})
    assert first.receive_json()["type"] == "pong" and second is not None


def test_a_person_who_is_revoked_while_connected_is_ended_at_once(
    client: TestClient, chat: Chat, world: World
) -> None:
    socket = ready(client, chat.p_token)
    chat.provider.person.status = "revoked"
    chat.provider.person.home_group_id = None
    world.session.flush()
    socket.send_json({"type": "ping"})
    assert closed_with(socket) == 4403


def test_an_event_for_a_person_who_may_no_longer_chat_ends_their_socket_instead(
    client: TestClient, chat: Chat, world: World, runtime: Any
) -> None:
    """A revoke between storing a message and delivering it: no message, only the close."""
    sender = ready(client, chat.s_token)
    receiver = ready(client, chat.p_token)
    sender.send_json({"type": "send", "conversation_id": chat.id, **new_message()})
    ack = next(f for f in (sender.receive_json(), sender.receive_json()) if f["type"] == "ack")
    assert receiver.receive_json()["type"] == "message"
    chat.provider.person.status = "revoked"
    chat.provider.person.home_group_id = None
    world.session.flush()
    event = {
        "kind": "message",
        "conversation_id": chat.id,
        "seq": ack["message"]["seq"],
        "people": [str(chat.provider.person.id)],
    }
    assert runtime.loop is not None
    asyncio.run_coroutine_threadsafe(runtime.dispatch(event), runtime.loop).result(timeout=10)
    assert closed_with(receiver) == 4403
    assert not runtime.hub.is_connected(chat.provider.person.id)


def test_a_message_to_a_revoked_person_is_refused_and_announces_nothing(
    client: TestClient, chat: Chat, world: World
) -> None:
    sender = ready(client, chat.s_token)
    chat.provider.person.status = "revoked"
    chat.provider.person.home_group_id = None
    world.session.flush()
    sender.send_json({"type": "send", "conversation_id": chat.id, **new_message()})
    assert sender.receive_json()["code"] == "chat_closed"


def test_the_hub_forgets_a_socket_when_it_closes(
    client: TestClient, chat: Chat, runtime: Any
) -> None:
    with client.websocket_connect(URL) as socket:
        socket.send_json({"type": "auth", "token": chat.s_token})
        socket.receive_json()
        assert runtime.hub.is_connected(chat.starter.person.id)
    assert not runtime.hub.is_connected(chat.starter.person.id)


def test_nothing_the_person_wrote_reaches_the_log(
    client: TestClient, chat: Chat, caplog: pytest.LogCaptureFixture
) -> None:
    sentence = "my-very-private-sentence"
    with caplog.at_level("DEBUG"):
        socket = ready(client, chat.s_token)
        socket.send_json({"type": "send", "conversation_id": chat.id, **new_message(body=sentence)})
        socket.receive_json()
        socket.send_text("garbage " + sentence)
        socket.receive_json()
    assert sentence not in caplog.text and chat.s_token not in caplog.text


def test_the_headers_helper_still_works_for_the_rest_api(client: TestClient, chat: Chat) -> None:
    assert headers_of(client, chat.starter)  # sanity: REST and the socket share the same login
