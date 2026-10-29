# Chat design (work host and freelancer)

Status: draft. Companion to [understanding](understanding.md) and [plan](plan.md). To be turned into an ADR ("ADR-0014 Real-time chat over WebSocket") and into the spec files 02, 03 and 04 as the first step of the chat work.

## 1. Requirements

| # | Requirement |
|---|---|
| C-01 | A work host can start a conversation with a freelancer from the search result or the detail page ("Message"). One conversation per pair. |
| C-02 | Both people send and read text messages in real time while the app is open, and see history when they come back. |
| C-03 | When the app is closed or in the background, the other person gets a push notification (no message text in the push). |
| C-04 | Unread counts per conversation and in total; read state is shared between the person's devices. |
| C-05 | A freelancer can mute, block and report a conversation. A block stops new messages in both directions. |
| C-06 | Abuse limits: new conversations per work host, messages per person per minute, message length. |
| C-07 | Works with several API processes (ECS later) and with one (Lightsail today). |
| C-08 | Works over a flaky mobile network: messages are never duplicated or lost, the app catches up after a reconnect. |
| C-09 | Same rules for authentication, roles, privacy and logging as the rest of the API. |
| C-10 | Words (names of roles) come from the installation's terminology; the server returns codes, not English sentences, for the app to translate. |

Out of scope for version 1: attachments, group chat, voice or video, typing indicators and online status (listed as later in section 9), message editing or deletion by users, web client.

## 2. Transport: WebSocket plus REST (gRPC considered)

| Option | For | Against | Verdict |
|---|---|---|---|
| **WebSocket** (FastAPI/Starlette, uvicorn already installed with `[standard]`) | Same process, same auth code, same deployment; works through Caddy and an AWS load balancer; a browser can use it later; Dart has first-class support | Reconnect and heartbeat logic written by us | **Chosen** |
| gRPC (bidirectional streaming) | Typed contract, efficient | Second server stack and port; needs HTTP/2 end to end (Caddy and ALB settings); browsers need gRPC-Web plus a proxy; the contract duplicates the OpenAPI types; more to secure and test | Not chosen |
| Server-Sent Events + REST POST | Simplest | One-way; mobile OS kills idle connections just as with WebSocket; no gain over WebSocket | Not chosen |
| Push only (FCM) | No connection to keep | Not real time enough, not reliable for ordering, text would pass through Google | Used **only** for wake-ups |

REST stays the source of truth: history, sending (as a fallback), read marks, lists. The WebSocket only carries **live events** and is an optimisation; if it is down, the app still works by polling the REST list when it comes to the foreground.

## 3. Data model (new tables, one migration)

All ids are UUID like the rest of the schema; `seq` gives a stable order for cursors.

```
conversations
  id uuid PK
  work_host_id uuid FK work_hosts ON DELETE SET NULL (anonymised, see 8)
  freelancer_id uuid FK freelancers ON DELETE SET NULL
  created_at timestamptz
  last_message_at timestamptz null          -- for ordering the list
  UNIQUE (work_host_id, freelancer_id)
  INDEX (freelancer_id, last_message_at DESC), (work_host_id, last_message_at DESC)

messages
  id uuid PK
  seq bigint GENERATED ALWAYS AS IDENTITY   -- order inside a conversation
  conversation_id uuid FK conversations ON DELETE CASCADE
  sender_type text CHECK ('workhost','freelancer')
  body text CHECK (length(body) BETWEEN 1 AND 2000)
  client_message_id uuid                    -- idempotency key from the app
  created_at timestamptz
  UNIQUE (conversation_id, sender_type, client_message_id)
  INDEX (conversation_id, seq)

conversation_state                          -- one row per side
  conversation_id uuid FK, side text ('workhost','freelancer')  PK together
  last_read_seq bigint default 0
  muted boolean default false
  blocked boolean default false             -- the freelancer side only is used in v1

chat_reports
  id uuid PK, conversation_id FK, reported_by_side text, reason text (code),
  note text null (max 500), created_at, handled_at null, handled_by_admin_id null

device_tokens                               -- shared with other push features
  id uuid PK, user_type text, user_id uuid, platform text ('android','ios'),
  token text UNIQUE, app_version text, created_at, last_seen_at

notification_outbox
  id uuid PK, user_type, user_id, kind text ('chat_message', later others),
  payload jsonb (ids only), created_at, send_after, sent_at null, attempts int, last_error text null
  INDEX (sent_at NULLS FIRST, send_after)
```

`created_at` for messages is set by the server only. Unread count for a side = messages with `seq > last_read_seq` sent by the other side.

## 4. REST API (additions to `docs/specification/04-api.md`)

Roles: `workhost` and `freelancer` only (organisation and admin get `403`, except the admin report endpoints in 7).

| Method | Path | Notes |
|---|---|---|
| POST | /chat/conversations | work host only. Body `freelancer_id`. Returns the existing conversation if there is one (`200`), otherwise creates it (`201`). `429 chat_new_conversation_limit` over the daily limit. `403 chat_blocked` if the freelancer blocked this host. |
| GET | /chat/conversations | Paginated, newest activity first. Each item: id, the other person's id and display name, last message preview length-limited (60 characters), `last_message_at`, `unread_count`, `muted`. |
| GET | /chat/conversations/{id}/messages?before_seq=&limit= | Newest first, `limit` at most 50, cursor `before_seq`. Only for the two participants, otherwise `404` (never reveal that it exists). |
| POST | /chat/conversations/{id}/messages | Body `client_message_id`, `body`. Idempotent: a repeated `client_message_id` returns the stored message (`200`). `201` for a new one. Same rules and rate limits as the WebSocket `send`. |
| POST | /chat/conversations/{id}/read | Body `up_to_seq`. Moves `last_read_seq` forward only. |
| PUT | /chat/conversations/{id}/settings | Body `muted`, `blocked` (blocked only for a freelancer). |
| POST | /chat/conversations/{id}/report | Body `reason` (code), optional `note`. Creates a `chat_reports` row. |
| GET | /chat/unread | `{ "total": n }` for the badge. |
| POST | /devices | Register a push token: `platform`, `token`, `app_version`. Idempotent. |
| DELETE | /devices/{id} | At logout. |
| GET | /chat/ws-info | Optional: returns the WebSocket URL and the heartbeat interval, so the app does not hard-code them. |

Errors use the standard envelope with stable codes: `chat_blocked`, `chat_not_allowed`, `chat_message_too_long`, `chat_rate_limited`, `chat_new_conversation_limit`.

## 5. WebSocket protocol

Endpoint: `wss://<host>/api/v1/chat/ws`. JSON text frames. Protocol version `1`; a breaking change would be a new path.

**Authentication.** The token is never put in the address (addresses end up in logs). The first frame must be `{"type":"auth","token":"<access token>"}` within 5 seconds, otherwise the server closes with code `4401`. The access token expires after 15 minutes: the server closes with `4401` at expiry and the app refreshes the token with the normal refresh flow and reconnects. (Alternative if this proves awkward: `POST /chat/ws-ticket` returns a single-use ticket valid for 30 seconds that is sent as the first frame; decide in the ADR.)

Client to server:

| type | fields | meaning |
|---|---|---|
| `auth` | `token` | first frame |
| `send` | `conversation_id`, `client_message_id`, `body` | send a message |
| `read` | `conversation_id`, `up_to_seq` | mark read |
| `ping` | | heartbeat every 25 seconds |

Server to client:

| type | fields | meaning |
|---|---|---|
| `ready` | `server_time`, `heartbeat_seconds` | authentication accepted |
| `ack` | `client_message_id`, `message` | the message was stored (the full stored message) |
| `message` | `message` | a new message from the other person (also sent to the sender's other devices) |
| `read` | `conversation_id`, `side`, `up_to_seq` | the other side read up to here |
| `error` | `code`, optional `client_message_id` | a request was refused (rate limit, blocked, too long ...) |
| `pong` | | heartbeat reply |

A `message` object: `id`, `seq`, `conversation_id`, `sender_side`, `body`, `created_at`.

Close codes: `4401` not authenticated or token expired, `4403` role not allowed, `4429` too many frames (the connection is closed, not only refused), `1001` server restart (reconnect with back-off), `1009` frame too large (limit 8 KiB).

**Catch-up after a reconnect.** The app remembers the highest `seq` it has per conversation, and after `ready` it calls `GET /chat/conversations` and, for each conversation with a newer `last_message_at`, `GET .../messages?before_seq=` until it reaches known messages. No special replay frame is needed, so the WebSocket stays simple.

**Sending is acknowledged.** The app shows a message as "sending" until the `ack` (or the REST response) arrives and retries with the same `client_message_id` after a timeout. The unique constraint makes retries safe.

## 6. Server design

- **Where the code lives.** `backend/app/api/v1/chat.py` (REST), `backend/app/chat/` (hub, ws handler, rules, notifier), models in `backend/app/models/chat.py`, one Alembic migration, schemas in `backend/app/schemas/chat.py`.
- **Connection hub.** Each API process keeps a map `(user_type, user_id) -> set of sockets`. Delivering an event to a person sends it to every socket they have in this process.
- **Several processes.** After a message is stored the process runs `NOTIFY chat_events, '<json with ids only>'` in the same transaction. Every process holds one dedicated connection that `LISTEN`s and forwards the events to the sockets it has. This keeps PostgreSQL the only infrastructure (ADR-0002); payload is ids only (limit 8 000 bytes) and the message is read from the database by the receiver process. If the LISTEN connection drops, the process reconnects and the app's catch-up covers any gap. Redis is deliberately not added; revisit only if LISTEN/NOTIFY becomes a bottleneck.
- **Sync SQLAlchemy and async WebSocket.** The code base uses synchronous SQLAlchemy sessions. WebSocket handlers are async. Run database work from the handler with `run_in_threadpool`, keep sessions short, and use one separate async (or raw) connection only for LISTEN. The first task of the chat work is a small spike that proves this under load (section 8 of the plan). If it does not hold, the alternative is a small async engine used only by `chat`.
- **Rules (one module, used by REST and WebSocket alike).** Both ids exist; the caller is one of the two people; the freelancer has not blocked; length 1 to 2000 after trimming; no control characters other than newline; rate limits; then store, update `last_message_at`, create outbox rows, NOTIFY.
- **Limits (settings with defaults, like the reveal limits):** `CHAT_MAX_NEW_CONVERSATIONS_PER_DAY=10` per work host, `CHAT_MAX_MESSAGES_PER_MINUTE=20` per person, `CHAT_MAX_MESSAGE_CHARS=2000`, `CHAT_MAX_SOCKETS_PER_USER=5`. They are the only settings with defaults, like `REVEAL_MAX_*`.
- **Push.** After storing a message the server writes a `notification_outbox` row for the recipient **unless** the recipient has an open socket in any process or has muted the conversation. The existing worker process sends the push via FCM (HTTP v1 API) and removes tokens that FCM reports as invalid. A failed push is retried a few times and never blocks the sender. The push is an FCM notification message with a fixed generic text ("You have a new message") plus data fields (`kind=chat_message`, conversation id), so it shows reliably when the app is closed; no message text and no sender name pass through Google. Whether a name may be shown is a later user setting.
- **Device tokens.** Stored as received (FCM needs the real token). They are not passwords but must never be logged. Logging rules below apply.
- **Secrets.** The Firebase service-account key is an environment variable (a file path or the JSON in a `SecretStr`), registered with the log redactor like the other secrets, and checked by `validate_secrets` in strict environments only when push is enabled (`PUSH_ENABLED=true`).
- **Logging.** Never log message bodies, tokens (access, refresh, device) or phone numbers. Log ids, event types, durations and error codes only. Add a test like `test_logging_redaction.py` for the chat paths.
- **Reverse proxy.** Caddy proxies WebSocket upgrades without extra configuration; check that no idle timeout shorter than the heartbeat is set. Behind AWS load balancers set the idle timeout above 60 seconds. Document in the runbook.

## 7. Moderation and admin

- A report stores a row; the web admin gets a **Chat reports** report (new, RP-09: reports per week, per reason, open vs handled) and an admin-only endpoint `GET /admin/chat-reports` and `GET /admin/chat-reports/{id}/messages` that returns the reported conversation, **each access logged** with the admin id. Admins cannot browse other conversations (open question Q-A3).
- Blocking a freelancer-side conversation makes `POST .../messages` from the work host return `403 chat_blocked`. The work host is not told more than that.
- Chat metrics report (new, RP-10): conversations started, messages per day, first reply rate and median time to first reply, per work host and per skill (through the freelancer's skills), reveal-to-conversation conversion (a conversation started after a reveal of the same freelancer by the same host). This extends the reveal analysis (RP-08).

## 8. Privacy, deletion and retention

- Messages are visible to the two participants only (plus the reported-conversation exception).
- Deleting an account: that person's side becomes anonymous ("Deleted account"), the other person keeps the history; if both are deleted the conversation and its messages are removed. Decide with the privacy page (Q-A4).
- Export and "delete this conversation for me" are later.
- The privacy page and the store data-safety form must be updated before the first chat release (messages, device tokens).

## 9. Later (not version 1)

Typing indicator and online status, attachments (photos), message deletion, "report and block" in one step, quick replies, chat on the web, delivery receipts per device, search in messages, end-to-end encryption (would remove admin access to reports; a product decision).

## 10. Test plan (summary; details in plan section 8)

- Unit: rules module (length, trimming, blocked, limits), idempotency, cursor pagination, unread arithmetic.
- API: every REST endpoint for every role (allowed, forbidden, not participant -> 404), rate limits with small test limits (set directly in `conftest.py`, as for the reveal limits).
- WebSocket: with Starlette's `TestClient.websocket_connect` for auth timeout, bad token, expired token, role not allowed, send/ack/message between two clients, a second device receiving the sender's own message, rate-limit close, oversize frame, reconnect catch-up through REST.
- Multi-process: a test that starts two hub instances sharing one database and shows that a message stored through one reaches a socket on the other (LISTEN/NOTIFY).
- Logging: a test proving bodies, tokens and numbers do not reach logs.
- Android: unit tests for the message queue (retry, dedupe by `client_message_id`), widget tests for the conversation list and thread (states: empty, loading, error, sending, failed), integration test with a fake WebSocket server.
