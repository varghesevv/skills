from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api import health
from app.api.v1 import api_v1_router
from app.chat.runtime import ChatRuntime
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.errors import register_error_handlers
from app.core.logging_config import configure_logging
from app.core.version import APP_VERSION
from app.services import database_setup, initial_config


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """First the tables, created only when the database has none (a new installation). Then the
    initial config (story S100): applied to an empty database or checked against a set-up one; a
    file that does not match stops the start-up. Then chat: one listener connection
    per process (ADR-0014), started in the background and retried, so a database that is slow or
    still starting never stops the API. Without a database address (some tests) neither runs."""
    settings = get_settings()
    runtime: ChatRuntime | None = None
    if settings.database_url is not None and settings.database_url.get_secret_value():
        # A new installation gets its tables, then the initial config: when the config does not
        # match the database the API does not start.
        if settings.create_tables_at_startup:
            await run_in_threadpool(
                database_setup.create_tables_if_missing, settings.require_database_url()
            )
        await run_in_threadpool(initial_config.run_at_startup, settings, get_session_factory())
        runtime = ChatRuntime(
            settings.require_database_url(),
            get_session_factory(),
            max_sockets_per_person=settings.chat_max_sockets_per_person,
        )
        await runtime.start(wait=False)
    app.state.chat = runtime
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Skills API", version=APP_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(api_v1_router)
    return app


app = create_app()
