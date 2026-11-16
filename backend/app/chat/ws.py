"""The WebSocket of chat (ADR-0014): `wss://<host>/api/v1/chat/ws`, JSON text frames.

Authentication is the first frame, never the address. Every frame re-reads the person, so a
revoked or closed person is ended at once; the access token's expiry ends the socket too. REST
does everything the socket does, so the socket is an optimisation, not the only way.
"""

import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.chat import rules
from app.chat.hub import TooManySockets
from app.chat.runtime import ChatRuntime, SessionFactory, Who, load_who
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import TokenError, decode_access_token_with_expiry
from app.models.church import Person

logger = logging.getLogger(__name__)

AUTH_WAIT_SECONDS = 5
HEARTBEAT_SECONDS = 25
IDLE_SECONDS = 70  # no frame at all (not even a ping) for this long: the connection is dead
MAX_FRAME_BYTES = 8 * 1024
FRAMES_PER_WINDOW = 60
WINDOW_SECONDS = 10

CLOSE_NOT_AUTHENTICATED = 4401
CLOSE_NOT_ALLOWED = 4403
CLOSE_TOO_MANY = 4429
CLOSE_TOO_BIG = 1009
CLOSE_GOING_AWAY = 1001
CLOSE_UNSUPPORTED = 1003  # a binary frame: only JSON text is spoken here


def _uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def _read(websocket: WebSocket) -> str | None:
    """The next text frame; None for a binary frame. Raises WebSocketDisconnect when it closes."""
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    text = message.get("text")
    return text if isinstance(text, str) else None


async def serve(
    websocket: WebSocket, runtime: ChatRuntime, factory: SessionFactory, settings: Settings
) -> None:
    await websocket.accept()
    try:
        first = await asyncio.wait_for(_read(websocket), AUTH_WAIT_SECONDS)
    except (TimeoutError, WebSocketDisconnect):
        await _close(websocket, CLOSE_NOT_AUTHENTICATED)
        return
    if first is None:  # binary
        await _close(websocket, CLOSE_NOT_AUTHENTICATED)
        return
    if len(first.encode()) > MAX_FRAME_BYTES:  # before parsing: this frame needs no account
        await _close(websocket, CLOSE_TOO_BIG)
        return
    try:
        frame = json.loads(first)
        token = frame["token"] if frame.get("type") == "auth" else None
        principal, expires = decode_access_token_with_expiry(
            str(token), secret=settings.require_jwt_secret()
        )
    except (ValueError, KeyError, TypeError, AttributeError, TokenError):
        await _close(websocket, CLOSE_NOT_AUTHENTICATED)
        return
    who = await run_in_threadpool(load_who, factory, principal.user_id)
    if who is None:
        await _close(websocket, CLOSE_NOT_ALLOWED)
        return

    async def send(frame: dict[str, Any]) -> None:
        await websocket.send_json(frame)

    async def close(code: int) -> None:
        await _close(websocket, code)

    try:
        handle = runtime.hub.connect(who.id, send, close)
    except TooManySockets:
        await _close(websocket, CLOSE_TOO_MANY)
        return
    try:
        await send({"type": "ready", "server_time": _now(), "heartbeat_seconds": HEARTBEAT_SECONDS})
        await _loop(websocket, runtime, factory, settings, who, expires, send)
    except WebSocketDisconnect:
        pass
    finally:
        runtime.hub.disconnect(who.id, handle)


async def _loop(
    websocket: WebSocket,
    runtime: ChatRuntime,
    factory: SessionFactory,
    settings: Settings,
    who: Who,
    expires: datetime,
    send: Any,
) -> None:
    recent: deque[float] = deque()
    while True:
        remaining = (expires - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            await _close(websocket, CLOSE_NOT_AUTHENTICATED)  # the app refreshes and reconnects
            return
        try:
            text = await asyncio.wait_for(_read(websocket), min(IDLE_SECONDS, remaining))
        except TimeoutError:
            if (expires - datetime.now(UTC)).total_seconds() <= 0:
                await _close(websocket, CLOSE_NOT_AUTHENTICATED)
            else:
                await _close(websocket, CLOSE_GOING_AWAY)
            return
        if text is None:
            await _close(websocket, CLOSE_UNSUPPORTED)
            return
        if len(text.encode()) > MAX_FRAME_BYTES:
            await _close(websocket, CLOSE_TOO_BIG)
            return
        now = time.monotonic()
        recent.append(now)
        while recent and recent[0] < now - WINDOW_SECONDS:
            recent.popleft()
        if len(recent) > FRAMES_PER_WINDOW:
            await _close(websocket, CLOSE_TOO_MANY)
            return
        # The person is read again on every frame (ping included): a revoke ends the socket.
        if await run_in_threadpool(load_who, factory, who.id) is None:
            await _close(websocket, CLOSE_NOT_ALLOWED)
            return
        await _handle(text, runtime, factory, settings, who, send)


async def _handle(
    text: str,
    runtime: ChatRuntime,
    factory: SessionFactory,
    settings: Settings,
    who: Who,
    send: Any,
) -> None:
    try:
        frame = json.loads(text)
        kind = frame["type"]
    except (ValueError, KeyError, TypeError):
        await send({"type": "error", "code": "bad_frame"})
        return
    if kind == "ping":
        await send({"type": "pong"})
        return
    conversation_id = _uuid(frame.get("conversation_id"))
    client_id = frame.get("client_message_id")
    try:
        if conversation_id is None:
            raise ApiError(422, "bad_frame", "A conversation id is needed")
        if kind == "send":
            cid = _uuid(client_id)
            body = frame.get("body")
            if cid is None or not isinstance(body, str):
                raise ApiError(422, "bad_frame", "A message needs an id and a text")
            message = await run_in_threadpool(
                _send, factory, settings, who, conversation_id, cid, body
            )
            await send({"type": "ack", "client_message_id": str(cid), "message": message})
        elif kind in ("read", "delivered"):
            seq = frame.get("up_to_seq")
            if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
                raise ApiError(422, "bad_frame", "up_to_seq must be a number")
            await run_in_threadpool(_mark, factory, who, conversation_id, kind, seq)
        else:
            raise ApiError(422, "bad_frame", "Unknown frame")
    except ApiError as error:
        reply: dict[str, Any] = {"type": "error", "code": error.code}
        if isinstance(client_id, str):
            reply["client_message_id"] = client_id
        await send(reply)
    except Exception:
        logger.exception("chat frame failed")  # no body, no token
        await send({"type": "error", "code": "server_error"})


def _send(
    factory: SessionFactory,
    settings: Settings,
    who: Who,
    conversation_id: uuid.UUID,
    client_message_id: uuid.UUID,
    body: str,
) -> dict[str, Any]:
    with factory() as db:
        person = db.get(Person, who.id)
        if person is None:
            raise ApiError(404, "not_found", "Conversation not found")
        conversation, side = rules.open_conversation(db, conversation_id, person)
        message, _created = rules.send_message(
            db, settings, conversation, side, person, client_message_id, body
        )
        db.commit()
        return rules.message_out(message).model_dump(mode="json")


def _mark(
    factory: SessionFactory, who: Who, conversation_id: uuid.UUID, kind: str, seq: int
) -> None:
    with factory() as db:
        person = db.get(Person, who.id)
        if person is None:
            raise ApiError(404, "not_found", "Conversation not found")
        conversation, side = rules.open_conversation(db, conversation_id, person)
        if kind == "read":
            rules.mark_read(db, conversation, side, seq)
        else:
            rules.mark_delivered(db, conversation, side, seq)
        db.commit()


async def _close(websocket: WebSocket, code: int) -> None:
    with contextlib.suppress(RuntimeError):  # already closed
        await websocket.close(code=code)


def _now() -> str:
    return datetime.now(UTC).isoformat()
