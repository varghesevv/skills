"""The chat parts of one API process: the hub, the listener and the delivery of events.

An event arrives from PostgreSQL (`NOTIFY`, ids only). For each person on it who holds a socket in
this process the frame is built from the database, after checking that the person is still open,
and sent. A person who is no longer open has their sockets closed instead of receiving anything.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.chat.hub import Frame, Hub
from app.chat.listener import Listener
from app.chat.rules import message_out
from app.models.chat import Message
from app.models.church import Person

logger = logging.getLogger(__name__)

CLOSE_NOT_ALLOWED = 4403

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class Who:
    """What the socket handler needs to know about a person."""

    id: uuid.UUID
    status: str


def load_who(factory: SessionFactory, person_id: uuid.UUID) -> Who | None:
    """The person, or None when they may not use chat now (gone, closed, revoked, not admitted)."""
    with factory() as db:
        person = db.get(Person, person_id)
        if (
            person is None
            or person.closed_at is not None
            or person.status in ("revoked", "pending")
        ):
            return None
        return Who(person.id, person.status)


class ChatRuntime:
    def __init__(
        self, database_url: str, factory: SessionFactory, *, max_sockets_per_person: int = 5
    ) -> None:
        self.hub = Hub(max_sockets_per_person)
        self.factory = factory
        self.listener = Listener(database_url, self.dispatch)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def start(self, *, wait: bool = False) -> None:
        self.loop = asyncio.get_running_loop()
        await self.listener.start(wait=wait)

    async def stop(self) -> None:
        await self.listener.stop()
        await self.hub.close_all()

    async def dispatch(self, event: dict[str, Any]) -> None:
        """Deliver an event to the sockets of this process (every event of the database)."""
        people = [uuid.UUID(raw) for raw in event.get("people", [])]
        local = [p for p in people if self.hub.is_connected(p)]
        if not local:
            return
        built = await run_in_threadpool(self._build, event, local)
        for person_id, frame in built:
            if frame is None:
                await self.hub.close_person(person_id, CLOSE_NOT_ALLOWED)
            else:
                await self.hub.deliver(person_id, frame)

    def _build(
        self, event: dict[str, Any], people: list[uuid.UUID]
    ) -> list[tuple[uuid.UUID, Frame | None]]:
        kind = event.get("kind")
        with self.factory() as db:
            frame = self._frame(db, event, kind)
        if frame is None:
            return []
        out: list[tuple[uuid.UUID, Frame | None]] = []
        for person_id in people:
            # A person who may no longer chat gets nothing, and their sockets end.
            out.append((person_id, frame if load_who(self.factory, person_id) else None))
        return out

    @staticmethod
    def _frame(db: Session, event: dict[str, Any], kind: object) -> Frame | None:
        if kind == "message":
            message = db.scalar(
                select(Message).where(
                    Message.conversation_id == uuid.UUID(event["conversation_id"]),
                    Message.seq == int(event["seq"]),
                )
            )
            if message is None:
                return None
            return {"type": "message", "message": message_out(message).model_dump(mode="json")}
        if kind in ("read", "delivered"):
            return {
                "type": kind,
                "conversation_id": event["conversation_id"],
                "side": event["side"],
                "up_to_seq": int(event["up_to_seq"]),
            }
        return None
