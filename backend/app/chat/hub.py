"""The sockets of one API process, and the delivery of an event to the people who hold them.

A process knows only its own sockets. An event for a person is announced to every process through
PostgreSQL (`NOTIFY`, see `listener.py`); each process delivers it to the sockets it holds. Nothing
here depends on which process stored the message, so it is correct with one process or ten.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

Frame = dict[str, Any]
Send = Callable[[Frame], Awaitable[None]]


class TooManySockets(Exception):
    """A person already holds the most sockets one process allows."""


class Hub:
    def __init__(self, max_sockets_per_person: int = 5) -> None:
        self._max = max_sockets_per_person
        self._sockets: dict[uuid.UUID, dict[int, Send]] = {}
        self._next = 0

    def connect(self, person_id: uuid.UUID, send: Send) -> int:
        """Register a socket; returns a handle for `disconnect`."""
        held = self._sockets.setdefault(person_id, {})
        if len(held) >= self._max:
            raise TooManySockets
        self._next += 1
        held[self._next] = send
        return self._next

    def disconnect(self, person_id: uuid.UUID, handle: int) -> None:
        held = self._sockets.get(person_id)
        if held is None:
            return
        held.pop(handle, None)
        if not held:
            del self._sockets[person_id]

    def is_connected(self, person_id: uuid.UUID) -> bool:
        return person_id in self._sockets

    def connected_people(self) -> set[uuid.UUID]:
        return set(self._sockets)

    async def deliver(self, person_id: uuid.UUID, frame: Frame) -> int:
        """Send a frame to every socket of the person in this process; returns how many."""
        sent = 0
        for handle, send in list(self._sockets.get(person_id, {}).items()):
            try:
                await send(frame)
                sent += 1
            except Exception:  # a dead socket must not stop the others; its handler cleans up
                logger.info("chat socket send failed", extra={"handle": handle})
        return sent

    async def close_all(self) -> None:
        """Forget every socket (the process is stopping)."""
        self._sockets.clear()
        await asyncio.sleep(0)
