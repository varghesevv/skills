"""The chat plumbing (ADR-0014 spike): a message stored through one process reaches a socket held
by another, over PostgreSQL LISTEN/NOTIFY, with synchronous database work next to an async loop."""

import asyncio
import os
import time
import uuid
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.chat.hub import Hub, TooManySockets
from app.chat.listener import MAX_PAYLOAD_BYTES, Listener, notify

pytestmark = pytest.mark.db


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


@pytest.fixture(scope="module", autouse=True)
def warm_connection() -> None:
    """The first connection to a freshly started database can take long on a loaded host (about 11
    seconds in the development container); make it here, not inside a timeout of the tests."""
    engine = create_engine(database_url())
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()


class Process:
    """One API process: its own hub and its own listener connection."""

    def __init__(self, url: str) -> None:
        self.hub = Hub()
        self.received: list[tuple[uuid.UUID, dict[str, Any]]] = []

        async def on_event(event: dict[str, Any]) -> None:
            for raw in event["people"]:
                person = uuid.UUID(raw)
                await self.hub.deliver(person, event)

        self.listener = Listener(url, on_event)

    def attach(self, person: uuid.UUID) -> list[dict[str, Any]]:
        frames: list[dict[str, Any]] = []

        async def send(frame: dict[str, Any]) -> None:
            frames.append(frame)

        self.hub.connect(person, send)
        return frames


def announce(url: str, event: dict[str, Any]) -> None:
    """What the process that stores a message does: NOTIFY in a transaction that commits."""
    engine = create_engine(url)
    with Session(engine) as session, session.begin():
        notify(session, event)
    engine.dispose()


async def eventually(check: Any, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("did not happen in time")


def test_a_message_stored_by_one_process_reaches_a_socket_of_another() -> None:
    url = database_url()
    person = uuid.uuid4()

    async def scenario() -> None:
        a, b = Process(url), Process(url)
        await a.listener.start()
        await b.listener.start()
        try:
            frames = b.attach(person)  # the person's phone is connected to process B only
            await run_in_threadpool(
                announce, url, {"kind": "message", "people": [str(person)], "seq": 1}
            )  # process A stores the message
            await eventually(lambda: len(frames) == 1)
            assert frames[0]["seq"] == 1
        finally:
            await a.listener.stop()
            await b.listener.stop()

    asyncio.run(scenario())


def test_every_process_delivers_to_its_own_sockets_and_nobody_else() -> None:
    url = database_url()
    mine, other = uuid.uuid4(), uuid.uuid4()

    async def scenario() -> None:
        a, b = Process(url), Process(url)
        await a.listener.start()
        await b.listener.start()
        try:
            on_a, on_b, bystander = a.attach(mine), b.attach(mine), b.attach(other)
            await run_in_threadpool(announce, url, {"people": [str(mine)], "seq": 7})
            await eventually(lambda: len(on_a) == 1 and len(on_b) == 1)
            await asyncio.sleep(0.2)
            assert bystander == []
        finally:
            await a.listener.stop()
            await b.listener.stop()

    asyncio.run(scenario())


def test_a_rolled_back_transaction_announces_nothing() -> None:
    url = database_url()
    person = uuid.uuid4()

    async def scenario() -> None:
        a = Process(url)
        await a.listener.start()
        try:
            frames = a.attach(person)

            def rolled_back() -> None:
                engine = create_engine(url)
                with Session(engine) as session:
                    notify(session, {"people": [str(person)], "seq": 1})
                    session.rollback()
                engine.dispose()

            await run_in_threadpool(rolled_back)
            await asyncio.sleep(0.3)
            assert frames == []
        finally:
            await a.listener.stop()

    asyncio.run(scenario())


def test_the_listener_comes_back_after_its_connection_is_killed() -> None:
    url = database_url()
    person = uuid.uuid4()

    async def scenario() -> None:
        a = Process(url)
        await a.listener.start()
        try:
            frames = a.attach(person)

            pid = a.listener.backend_pid
            assert pid is not None

            def kill_listener() -> None:
                engine = create_engine(url)
                with engine.begin() as connection:
                    connection.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
                engine.dispose()

            await run_in_threadpool(kill_listener)
            await eventually(lambda: a.listener.reconnects >= 1)
            await asyncio.wait_for(a.listener.listening.wait(), timeout=5)
            await run_in_threadpool(announce, url, {"people": [str(person)], "seq": 2})
            await eventually(lambda: len(frames) == 1)
        finally:
            await a.listener.stop()

    asyncio.run(scenario())


def test_slow_synchronous_database_work_does_not_stall_the_event_loop() -> None:
    url = database_url()

    async def scenario() -> None:
        ticks = 0

        async def heartbeat() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        def slow_query() -> None:
            engine = create_engine(url)
            with engine.connect() as connection:
                connection.execute(text("SELECT pg_sleep(0.6)"))
            engine.dispose()

        task = asyncio.create_task(heartbeat())
        await asyncio.gather(*(run_in_threadpool(slow_query) for _ in range(4)))
        task.cancel()
        assert ticks >= 8  # about 12 in 0.6 s: the loop kept running while four queries slept

    asyncio.run(scenario())


def test_a_person_cannot_hold_more_sockets_than_allowed() -> None:
    hub = Hub(max_sockets_per_person=2)
    person = uuid.uuid4()

    async def send(frame: dict[str, Any]) -> None:  # pragma: no cover - never called
        raise AssertionError

    first = hub.connect(person, send)
    hub.connect(person, send)
    with pytest.raises(TooManySockets):
        hub.connect(person, send)
    hub.disconnect(person, first)
    hub.connect(person, send)  # a slot is free again
    assert hub.is_connected(person)


def test_closing_a_person_ends_every_socket_of_theirs_and_only_theirs() -> None:
    hub = Hub()
    gone, stays = uuid.uuid4(), uuid.uuid4()
    codes: list[tuple[str, int]] = []

    def closer(name: str) -> Any:
        async def close(code: int) -> None:
            codes.append((name, code))

        return close

    async def send(frame: dict[str, Any]) -> None:  # pragma: no cover
        raise AssertionError

    hub.connect(gone, send, closer("phone"))
    hub.connect(gone, send, closer("tablet"))
    hub.connect(stays, send, closer("other"))
    assert asyncio.run(hub.close_person(gone, 4403)) == 2
    assert sorted(codes) == [("phone", 4403), ("tablet", 4403)]
    assert not hub.is_connected(gone) and hub.is_connected(stays)


def test_a_dead_socket_does_not_stop_the_others() -> None:
    hub = Hub()
    person = uuid.uuid4()
    got: list[dict[str, Any]] = []

    async def dead(frame: dict[str, Any]) -> None:
        raise RuntimeError("closed")

    async def alive(frame: dict[str, Any]) -> None:
        got.append(frame)

    hub.connect(person, dead)
    hub.connect(person, alive)
    assert asyncio.run(hub.deliver(person, {"x": 1})) == 1
    assert got == [{"x": 1}]


def test_an_event_that_is_too_large_is_refused() -> None:
    url = database_url()
    engine = create_engine(url)
    with Session(engine) as session, pytest.raises(ValueError):
        notify(session, {"blob": "x" * (MAX_PAYLOAD_BYTES + 10)})
    engine.dispose()
