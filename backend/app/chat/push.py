"""Push for chat (S8.5, ADR-0014): the outbox, the cancel rule and the sender.

Storing a message adds (or raises) one outbox row for the recipient, due after
`CHAT_PUSH_DELAY_SECONDS`. The worker looks at due rows: if the person's process already
delivered the message to a socket (`delivered_seq`) the row is cancelled; otherwise one generic
push goes to each of their devices. The push never carries message text or names.
"""

import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

import httpx
import jwt
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging_config import register_secret
from app.models.chat import (
    Conversation,
    ConversationState,
    DeviceToken,
    PushOutbox,
)
from app.models.church import Person

log = logging.getLogger("skills.push")

SessionFactory = Callable[[], AbstractContextManager[Session]]
Result = Literal["ok", "invalid", "retry"]

TITLE = "Skills"
BODY_ONE = "You have a new message"
BODY_MANY = "You have new messages"
MAX_ATTEMPTS = 5
RETRY_SECONDS = 30
BATCH = 50


class PushSender(Protocol):
    def send(self, token: str, title: str, body: str, data: dict[str, str]) -> Result: ...


# ---- the outbox -------------------------------------------------------------------------------


def enqueue(
    db: Session,
    settings: Settings,
    recipient: Person,
    conversation: Conversation,
    side: str,
    seq: int,
) -> None:
    """Note that the recipient has a message they may not have seen. Nothing is written when push
    is off, the conversation is muted by them, or they have no device. Same transaction as the
    message."""
    if not settings.push_enabled:
        return
    muted = db.scalar(
        select(ConversationState.muted).where(
            ConversationState.conversation_id == conversation.id, ConversationState.side == side
        )
    )
    if muted:
        return
    if not db.scalar(select(DeviceToken.id).where(DeviceToken.person_id == recipient.id).limit(1)):
        return
    due = func.now() + timedelta(seconds=settings.chat_push_delay_seconds)
    stmt = insert(PushOutbox).values(
        person_id=recipient.id,
        conversation_id=conversation.id,
        side=side,
        last_seq=seq,
        send_after=due,
    )
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["person_id", "conversation_id"],
            index_where=text("state = 'pending'"),
            set_={
                "last_seq": func.greatest(PushOutbox.last_seq, stmt.excluded.last_seq),
                "message_count": PushOutbox.message_count + 1,
            },
        )
    )


def _cancel(row: PushOutbox, reason: str, now: datetime) -> None:
    row.state, row.reason, row.finished_at = "cancelled", reason, now


def _decide(db: Session, row: PushOutbox) -> str | None:
    """Why this push is not needed any more, or None when it should be sent."""
    person = db.get(Person, row.person_id)
    if person is None or person.closed_at is not None or person.status == "revoked":
        return "closed"
    state = db.get(ConversationState, (row.conversation_id, row.side))
    if state is None:
        return "closed"
    if state.delivered_seq >= row.last_seq or state.last_read_seq >= row.last_seq:
        return "delivered"
    if state.muted:
        return "muted"
    provider = db.get(ConversationState, (row.conversation_id, "provider"))
    if provider is not None and provider.blocked:
        return "blocked"
    return None


def process_due(
    factory: SessionFactory, sender: PushSender, now: datetime | None = None
) -> dict[str, int]:
    """Handle every due row once (in batches); the counts of what happened, by outcome. Safe to run
    from more than one worker: rows are taken with `FOR UPDATE SKIP LOCKED`."""
    counts: dict[str, int] = {}
    while True:
        with factory() as db:
            moment = now or datetime.now(UTC)
            rows = db.scalars(
                select(PushOutbox)
                .where(PushOutbox.state == "pending", PushOutbox.send_after <= moment)
                .order_by(PushOutbox.send_after)
                .limit(BATCH)
                .with_for_update(skip_locked=True)
            ).all()
            if not rows:
                return counts
            for row in rows:
                outcome = _handle(db, sender, row, moment)
                counts[outcome] = counts.get(outcome, 0) + 1
            db.commit()
        if len(rows) < BATCH:
            return counts


def _handle(db: Session, sender: PushSender, row: PushOutbox, now: datetime) -> str:
    reason = _decide(db, row)
    if reason is not None:
        _cancel(row, reason, now)
        return reason
    devices = db.scalars(select(DeviceToken).where(DeviceToken.person_id == row.person_id)).all()
    if not devices:
        _cancel(row, "no_device", now)
        return "no_device"
    body = BODY_MANY if row.message_count > 1 else BODY_ONE
    data = {"type": "chat", "conversation_id": str(row.conversation_id)}
    delivered = retry = False
    for device in devices:
        result = sender.send(device.token, TITLE, body, data)
        if result == "ok":
            delivered = True
        elif result == "invalid":
            db.delete(device)  # the phone no longer has the app
        else:
            retry = True
    if delivered:
        row.state, row.finished_at = "sent", now
        return "sent"
    if not retry:  # every address was refused as unregistered
        _cancel(row, "no_device", now)
        return "no_device"
    row.attempts += 1
    if row.attempts >= MAX_ATTEMPTS:
        _cancel(row, "failed", now)
        return "failed"
    row.send_after = now + timedelta(seconds=RETRY_SECONDS)
    return "retry"


def purge_finished(db: Session, settings: Settings, now: datetime | None = None) -> int:
    """Delete outbox rows finished more than `CHAT_PUSH_KEEP_DAYS` ago."""
    limit = (now or datetime.now(UTC)) - timedelta(days=settings.chat_push_keep_days)
    result = db.execute(
        delete(PushOutbox).where(PushOutbox.state != "pending", PushOutbox.finished_at < limit)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


# ---- devices ----------------------------------------------------------------------------------


def register_device(
    db: Session, settings: Settings, person: Person, token: str, platform: str
) -> tuple[DeviceToken, bool]:
    """Remember a phone's address for the person; `(device, created)`. An address that belonged to
    someone else (a phone passed on, a second account) moves to this person. The oldest devices
    beyond `CHAT_MAX_DEVICES_PER_PERSON` are forgotten."""
    existing = db.scalar(select(DeviceToken).where(DeviceToken.token == token).with_for_update())
    now = datetime.now(UTC)
    if existing is not None:
        existing.person_id = person.id
        existing.last_seen_at = now
        db.flush()
        return existing, False
    device = DeviceToken(person_id=person.id, token=token, platform=platform)
    db.add(device)
    db.flush()
    keep = db.scalars(
        select(DeviceToken.id)
        .where(DeviceToken.person_id == person.id, DeviceToken.id != device.id)
        .order_by(DeviceToken.last_seen_at.desc(), DeviceToken.created_at.desc())
        .limit(settings.chat_max_devices_per_person - 1)
    ).all()
    db.execute(
        delete(DeviceToken).where(
            DeviceToken.person_id == person.id,
            DeviceToken.id != device.id,
            ~DeviceToken.id.in_(keep),
        )
    )
    db.refresh(device)
    return device, True


def forget_device(db: Session, person: Person, device_id: uuid.UUID) -> bool:
    result = db.execute(
        delete(DeviceToken).where(DeviceToken.id == device_id, DeviceToken.person_id == person.id)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


# ---- the sender -------------------------------------------------------------------------------

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_EXPIRES_EARLY = 60


class FcmSender:
    """Firebase Cloud Messaging, HTTP v1. The key file is read from the environment only."""

    def __init__(self, key_json: str, client: httpx.Client | None = None) -> None:
        key = json.loads(key_json)
        self._email: str = key["client_email"]
        self._private_key: str = key["private_key"]
        self._token_uri: str = key.get("token_uri", "https://oauth2.googleapis.com/token")
        self._project: str = key["project_id"]
        register_secret(self._private_key)
        self._http = client or httpx.Client(timeout=10.0)
        self._access: str | None = None
        self._expires = 0.0

    def _access_token(self) -> str:
        if self._access is not None and time.time() < self._expires - _EXPIRES_EARLY:
            return self._access
        issued = int(time.time())
        assertion = jwt.encode(
            {
                "iss": self._email,
                "scope": FCM_SCOPE,
                "aud": self._token_uri,
                "iat": issued,
                "exp": issued + 3600,
            },
            self._private_key,
            algorithm="RS256",
        )
        response = self._http.post(
            self._token_uri,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        response.raise_for_status()
        body = response.json()
        register_secret(str(body["access_token"]))
        self._access = str(body["access_token"])
        self._expires = time.time() + float(body.get("expires_in", 3600))
        return self._access

    def send(self, token: str, title: str, body: str, data: dict[str, str]) -> Result:
        message = {
            "message": {
                "token": token,
                "notification": {"title": title, "body": body},
                "data": data,
                "android": {"priority": "HIGH", "notification": {"channel_id": "chat"}},
            }
        }
        url = f"https://fcm.googleapis.com/v1/projects/{self._project}/messages:send"
        try:
            for attempt in (1, 2):
                response = self._http.post(
                    url, json=message, headers={"Authorization": f"Bearer {self._access_token()}"}
                )
                if response.status_code == 401 and attempt == 1:
                    self._access = None  # the access token expired early: get a new one
                    continue
                break
        except (httpx.HTTPError, KeyError, ValueError):
            log.warning("Push could not be sent (network or key problem)")
            return "retry"
        if response.status_code == 200:
            return "ok"
        if response.status_code == 404 or _unregistered(response):
            return "invalid"
        log.warning("Push refused with status %s", response.status_code)
        return "retry"


def _unregistered(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        details = response.json()["error"].get("details", [])
    except (ValueError, KeyError, AttributeError):
        return False
    return any(d.get("errorCode") == "UNREGISTERED" for d in details if isinstance(d, dict))


def build_sender(settings: Settings) -> PushSender:
    """The sender for the worker; stops it at start when push is on without a key."""
    key = settings.fcm_service_account_json
    if key is None or not key.get_secret_value():
        raise RuntimeError("PUSH_ENABLED is set but FCM_SERVICE_ACCOUNT_JSON is missing")
    return FcmSender(key.get_secret_value())
