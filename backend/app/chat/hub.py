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

SEND_TIMEOUT_SECONDS = 5.0  # a socket that takes longer than this to accept a frame is dropped

Frame = dict[str, Any]
Send = Callable[[Frame], Awaitable[None]]
Close = Callable[[int], Awaitable[None]]  # closes the socket with a WebSocket close code


class TooManySockets(Exception):
    """A person already holds the most sockets one process allows."""


class Hub:
    def __init__(
        self, max_sockets_per_person: int = 5, send_timeout: float = SEND_TIMEOUT_SECONDS
    ) -> None:
        self._max = max_sockets_per_person
        self._send_timeout = send_timeout
        self._closing: set[asyncio.Future[None]] = set()
        self._sockets: dict[uuid.UUID, dict[int, Send]] = {}
        self._closers: dict[tuple[uuid.UUID, int], Close] = {}
        self._next = 0

    def connect(self, person_id: uuid.UUID, send: Send, close: Close | None = None) -> int:
        """Register a socket; returns a handle for `disconnect`. `close` ends it from outside."""
        held = self._sockets.setdefault(person_id, {})
        if len(held) >= self._max:
            raise TooManySockets
        self._next += 1
        held[self._next] = send
        if close is not None:
            self._closers[(person_id, self._next)] = close
        return self._next

    def disconnect(self, person_id: uuid.UUID, handle: int) -> None:
        held = self._sockets.get(person_id)
        if held is None:
            return
        held.pop(handle, None)
        self._closers.pop((person_id, handle), None)
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
                # A phone that has stopped reading must not hold up everyone else's delivery.
                await asyncio.wait_for(send(frame), timeout=self._send_timeout)
                sent += 1
            except TimeoutError:
                logger.info("chat socket too slow, dropped", extra={"handle": handle})
                closer = self._closers.get((person_id, handle))
                self.disconnect(person_id, handle)
                if closer is not None:
                    # Closing writes to the same backed-up connection: do it on the side, so the
                    # delivery to the next socket does not wait for it.
                    task = asyncio.ensure_future(self._close_quietly(closer, handle))
                    self._closing.add(task)
                    task.add_done_callback(self._closing.discard)
            except Exception:  # a dead socket must not stop the others; its handler cleans up
                logger.info("chat socket send failed", extra={"handle": handle})
        return sent

    async def _close_quietly(self, closer: Close, handle: int) -> None:
        try:
            await asyncio.wait_for(closer(1013), timeout=self._send_timeout)
        except Exception:  # noqa: BLE001 - it is going away either way
            logger.info("chat socket close failed", extra={"handle": handle})

    async def close_person(self, person_id: uuid.UUID, code: int) -> int:
        """Close the person's sockets in this process (revoked, closed); returns how many."""
        closed = 0
        for handle in list(self._sockets.get(person_id, {})):
            closer = self._closers.get((person_id, handle))
            if closer is not None:
                try:
                    await closer(code)
                    closed += 1
                except Exception:
                    logger.info("chat socket close failed", extra={"handle": handle})
            self.disconnect(person_id, handle)
        return closed

    async def close_all(self) -> None:
        """Forget every socket (the process is stopping)."""
        self._sockets.clear()
        self._closers.clear()
        await asyncio.sleep(0)
