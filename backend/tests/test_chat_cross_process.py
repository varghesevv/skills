"""Two API processes on one database (ADR-0014): a message stored through one reaches a socket
held by the other, built from the database. The data is committed (PostgreSQL announces an event
only for a committed transaction), so this uses a database of its own, dropped afterwards."""

import asyncio
import os
import time
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from app.chat import rules
from app.chat.runtime import ChatRuntime
from app.core.config import get_settings
from app.core.security import hash_password
from tests.conftest import alembic_config, ensure_database
from tests.trust_helpers import World, make_person

pytestmark = pytest.mark.db

DB_NAME = "skills_chat_cross_process"


@pytest.fixture(scope="module")
def database() -> Iterator[tuple[str, Engine]]:
    base = os.environ.get("DATABASE_URL")
    if not base:
        pytest.skip("DATABASE_URL not set")
    url = ensure_database(base, DB_NAME)
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    yield url, engine
    engine.dispose()
    admin = create_engine(make_url(base).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def scene(database: tuple[str, Engine]) -> SimpleNamespace:
    """One church with its OWNER, made once and committed; each test adds its own people."""
    _, engine = database
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        world = World(session)
        session.commit()
        return SimpleNamespace(church=world.church, group=world.group)


class People:
    def __init__(self, engine: Engine, scene: SimpleNamespace) -> None:
        self.factory = sessionmaker(bind=engine, expire_on_commit=False)
        with self.factory() as session:
            password = hash_password(uuid.uuid4().hex)
            starter = make_person(scene.church, scene.group, "searcher", password_hash=password)
            provider = make_person(scene.church, scene.group, "provider", password_hash=password)
            session.add_all([starter, provider])
            session.commit()
            self.starter, self.provider = starter.id, provider.id

    def conversation(self) -> uuid.UUID:
        with self.factory() as db:
            from app.models.church import Person

            starter, provider = db.get(Person, self.starter), db.get(Person, self.provider)
            assert starter is not None and provider is not None
            conversation, _ = rules.start_conversation(db, get_settings(), starter, provider.id)
            db.commit()
            return conversation.id

    def send(self, conversation_id: uuid.UUID, body: str) -> int:
        from app.models.church import Person

        with self.factory() as db:
            starter = db.get(Person, self.starter)
            conversation, side = rules.open_conversation(db, conversation_id, starter)  # type: ignore[arg-type]
            message, _ = rules.send_message(
                db,
                get_settings(),
                conversation,
                side,
                starter,
                uuid.uuid4(),
                body,  # type: ignore[arg-type]
            )
            db.commit()
            return message.seq


async def eventually(check: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("did not happen in time")


def runtime(url: str, engine: Engine) -> ChatRuntime:
    return ChatRuntime(url, sessionmaker(bind=engine, expire_on_commit=False))


def attach(chat: ChatRuntime, person: uuid.UUID) -> tuple[list[dict[str, Any]], list[int]]:
    frames: list[dict[str, Any]] = []
    closed: list[int] = []

    async def send(frame: dict[str, Any]) -> None:
        frames.append(frame)

    async def close(code: int) -> None:
        closed.append(code)

    chat.hub.connect(person, send, close)
    return frames, closed


def test_a_message_stored_by_one_process_reaches_a_socket_of_the_other(
    database: tuple[str, Engine], scene: SimpleNamespace
) -> None:
    url, engine = database
    people = People(engine, scene)
    conversation = people.conversation()

    async def scenario() -> None:
        a, b = runtime(url, engine), runtime(url, engine)
        await a.start(wait=True)
        await b.start(wait=True)
        try:
            provider_frames, _ = attach(b, people.provider)  # the provider's phone is on process B
            starter_frames, _ = attach(a, people.starter)  # the sender's other device is on A
            seq = await run_in_threadpool(people.send, conversation, "Is Friday free?")
            await eventually(lambda: provider_frames and starter_frames)
            frame = provider_frames[0]
            assert frame["type"] == "message" and frame["message"]["seq"] == seq
            assert frame["message"]["body"] == "Is Friday free?"
            assert frame["message"]["sender_side"] == "starter"
            assert starter_frames[0]["message"]["id"] == frame["message"]["id"]
        finally:
            await a.stop()
            await b.stop()

    asyncio.run(scenario())


def test_a_revoke_that_is_committed_ends_the_socket_on_the_other_process(
    database: tuple[str, Engine], scene: SimpleNamespace
) -> None:
    url, engine = database
    people = People(engine, scene)
    conversation = people.conversation()

    async def scenario() -> None:
        a, b = runtime(url, engine), runtime(url, engine)
        await a.start(wait=True)
        await b.start(wait=True)
        try:
            frames, closed = attach(b, people.provider)
            # The provider is revoked after the message is stored but before it is delivered.
            seq = await run_in_threadpool(people.send, conversation, "Hello")
            await eventually(lambda: frames)
            frames.clear()

            def revoke() -> None:
                with people.factory() as db:
                    db.execute(
                        text(
                            "UPDATE people SET status = 'revoked', home_group_id = NULL "
                            "WHERE id = :i"
                        ),
                        {"i": people.provider},
                    )
                    db.commit()

            await run_in_threadpool(revoke)
            await a.dispatch(
                {
                    "kind": "message",
                    "conversation_id": str(conversation),
                    "seq": seq,
                    "people": [str(people.provider)],
                }
            )
            await b.dispatch(
                {
                    "kind": "message",
                    "conversation_id": str(conversation),
                    "seq": seq,
                    "people": [str(people.provider)],
                }
            )
            assert frames == [] and closed == [4403]
            assert not b.hub.is_connected(people.provider)
        finally:
            await a.stop()
            await b.stop()

    asyncio.run(scenario())


def test_a_read_mark_committed_by_one_process_reaches_the_other(
    database: tuple[str, Engine], scene: SimpleNamespace
) -> None:
    url, engine = database
    people = People(engine, scene)
    conversation = people.conversation()
    seq = people.send(conversation, "Read me")

    async def scenario() -> None:
        b = runtime(url, engine)
        await b.start(wait=True)
        try:
            starter_frames, _ = attach(b, people.starter)

            def provider_reads() -> None:
                from app.models.church import Person

                with people.factory() as db:
                    person = db.get(Person, people.provider)
                    conv, side = rules.open_conversation(db, conversation, person)  # type: ignore[arg-type]
                    rules.mark_read(db, conv, side, seq)
                    db.commit()

            await run_in_threadpool(provider_reads)
            await eventually(lambda: starter_frames)
            assert starter_frames[0] == {
                "type": "read",
                "conversation_id": str(conversation),
                "side": "provider",
                "up_to_seq": seq,
            }
        finally:
            await b.stop()

    asyncio.run(scenario())
