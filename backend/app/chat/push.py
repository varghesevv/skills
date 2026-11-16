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
from typing import Any, Literal, Protocol

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from sqlalchemy import delete, func, literal_column, select, text, update
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


LEASE_SECONDS = 120  # a claimed row is left alone this long (a worker that dies lets it go)


def _claim(factory: SessionFactory, moment: datetime) -> list[uuid.UUID]:
    """Take up to BATCH due rows by moving their time forward, in a short transaction, so that no
    row stays locked while the network is used."""
    with factory() as db:
        ids = list(
            db.scalars(
                select(PushOutbox.id)
                .where(PushOutbox.state == "pending", PushOutbox.send_after <= moment)
                .order_by(PushOutbox.send_after)
                .limit(BATCH)
                .with_for_update(skip_locked=True)
            )
        )
        if ids:
            db.execute(
                update(PushOutbox)
                .where(PushOutbox.id.in_(ids))
                .values(send_after=moment + timedelta(seconds=LEASE_SECONDS))
            )
        db.commit()
    return ids


def process_due(
    factory: SessionFactory, sender: PushSender, now: datetime | None = None
) -> dict[str, int]:
    """Handle every due row once; the counts of what happened, by outcome. Safe to run from more
    than one worker. A row is claimed in one short transaction, looked at in a second, sent with
    no transaction open, and its outcome written in a third, so a slow Firebase never blocks the
    sending of a message."""
    counts: dict[str, int] = {}
    moment = now or datetime.now(UTC)
    while True:
        ids = _claim(factory, moment)
        for row_id in ids:
            outcome = _process_one(factory, sender, row_id, moment)
            counts[outcome] = counts.get(outcome, 0) + 1
        if len(ids) < BATCH:
            return counts


def _process_one(
    factory: SessionFactory, sender: PushSender, row_id: uuid.UUID, now: datetime
) -> str:
    with factory() as db:  # look
        row = db.get(PushOutbox, row_id)
        if row is None or row.state != "pending":
            return "gone"
        reason = _decide(db, row)
        if reason is not None:
            _cancel(row, reason, now)
            db.commit()
            return reason
        seen_seq, count = row.last_seq, row.message_count
        devices = [
            (d.id, d.token)
            for d in db.scalars(select(DeviceToken).where(DeviceToken.person_id == row.person_id))
        ]
        if not devices:
            _cancel(row, "no_device", now)
            db.commit()
            return "no_device"
        db.commit()
    body = BODY_MANY if count > 1 else BODY_ONE
    data = {"type": "chat", "conversation_id": str(row.conversation_id)}
    results = [
        (device_id, sender.send(address, TITLE, body, data)) for device_id, address in devices
    ]
    with factory() as db:  # record
        row = db.scalar(select(PushOutbox).where(PushOutbox.id == row_id).with_for_update())
        if row is None:
            return "gone"
        gone = [device_id for device_id, result in results if result == "invalid"]
        if gone:
            db.execute(delete(DeviceToken).where(DeviceToken.id.in_(gone)))
        outcomes = {result for _, result in results}
        if "ok" in outcomes:
            if row.last_seq > seen_seq:
                # A newer message arrived while sending: it still needs its own push.
                row.send_after, row.message_count, row.attempts = now, 1, 0
                outcome = "sent"
            else:
                row.state, row.finished_at = "sent", now
                outcome = "sent"
        elif "retry" not in outcomes:  # every address was refused as unregistered
            _cancel(row, "no_device", now)
            outcome = "no_device"
        else:
            row.attempts += 1
            if row.attempts >= MAX_ATTEMPTS:
                _cancel(row, "failed", now)
                outcome = "failed"
            else:
                row.send_after = now + timedelta(seconds=RETRY_SECONDS)
                outcome = "retry"
        db.commit()
        return outcome


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
    # One statement, so two calls with the same new address cannot both insert it.
    stmt = insert(DeviceToken).values(person_id=person.id, token=token, platform=platform)
    inserted: Any = db.execute(
        stmt.on_conflict_do_update(
            index_elements=["token"],
            set_={"person_id": person.id, "last_seen_at": func.now(), "platform": platform},
        ).returning(DeviceToken.id, literal_column("(xmax = 0)").label("created"))
    ).one()
    device_id, created = inserted.id, bool(inserted.created)
    keep = db.scalars(
        select(DeviceToken.id)
        .where(DeviceToken.person_id == person.id, DeviceToken.id != device_id)
        .order_by(DeviceToken.last_seen_at.desc(), DeviceToken.created_at.desc())
        .limit(settings.chat_max_devices_per_person - 1)
    ).all()
    db.execute(
        delete(DeviceToken).where(
            DeviceToken.person_id == person.id,
            DeviceToken.id != device_id,
            ~DeviceToken.id.in_(keep),
        )
    )
    device = db.get(DeviceToken, device_id)
    if device is None:  # cannot happen: the row was just written
        raise RuntimeError("device row missing")
    db.refresh(device)
    return device, created


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
        # Fail at start, not at the first push, when the key cannot be used.
        serialization.load_pem_private_key(self._private_key.encode(), password=None)
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
        if _unregistered(response):
            return "invalid"
        log.warning("Push refused with status %s", response.status_code)
        return "retry"


def _unregistered(response: httpx.Response) -> bool:
    """Only the code UNREGISTERED means the phone's address is gone; a bare 404 may be a wrong
    project, and must not delete anyone's address."""
    if response.status_code not in (400, 404):
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
    try:
        return FcmSender(key.get_secret_value())
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON is not a usable service account key") from exc
