"""One dedicated PostgreSQL connection per process that LISTENs for chat events.

`notify` is called inside the transaction that stores a message, so PostgreSQL announces the event
only if that transaction commits. The payload holds ids only (never text): the receiver reads the
message from the database. A lost connection is re-opened with a growing pause; events announced
meanwhile are not replayed, which is fine because the app catches up through the REST list.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CHANNEL = "chat_events"
MAX_PAYLOAD_BYTES = 7900  # PostgreSQL refuses more than 8000

Handler = Callable[[dict[str, Any]], Awaitable[None]]


def notify(session: Session, event: dict[str, Any]) -> None:
    """Announce an event when the current transaction commits. Ids only."""
    payload = json.dumps(event, separators=(",", ":"))
    if len(payload.encode()) > MAX_PAYLOAD_BYTES:
        raise ValueError("chat event too large")
    session.execute(
        text("SELECT pg_notify(:channel, :payload)"), {"channel": CHANNEL, "payload": payload}
    )


def conninfo(database_url: str) -> str:
    """The libpq form of a SQLAlchemy URL (the `+psycopg` part is dropped)."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


class Listener:
    def __init__(self, database_url: str, handler: Handler, *, channel: str = CHANNEL) -> None:
        self._conninfo = conninfo(database_url)
        self._handler = handler
        self._channel = channel
        self._task: asyncio.Task[None] | None = None
        self.listening = asyncio.Event()  # set while LISTEN is active
        self.reconnects = 0

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="chat-listener")
        await asyncio.wait_for(self.listening.wait(), timeout=10)

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.listening.clear()

    async def _run(self) -> None:
        pause = 0.2
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self._conninfo, autocommit=True
                ) as connection:
                    await connection.execute(
                        sql.SQL("LISTEN {}").format(sql.Identifier(self._channel))
                    )
                    self.listening.set()
                    pause = 0.2
                    async for notification in connection.notifies():
                        await self._handle(notification.payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("chat listener lost its connection; retrying", exc_info=True)
            self.listening.clear()
            self.reconnects += 1
            await asyncio.sleep(pause)
            pause = min(pause * 2, 10.0)

    async def _handle(self, payload: str) -> None:
        try:
            event = json.loads(payload)
        except ValueError:
            logger.warning("chat event was not JSON")
            return
        if not isinstance(event, dict):
            return
        try:
            await self._handler(event)
        except Exception:  # one bad event must not end the listener
            logger.exception("chat event handler failed")
