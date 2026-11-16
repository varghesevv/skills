# ADR-0014: Real-time chat over WebSocket, announced through PostgreSQL

- Status: Accepted
- Date: 2026-11-16
- Deciders: Project owner

## Context

The app gets chat between a person who looks for a provider and the provider ([chat design](../android/chat-design.md)). It must work in real time while the app is open, give history and unread counts, wake a closed app with a notification, survive a flaky network without losing or duplicating a message, and work with one API process today (Lightsail) and several later (ECS, [ADR-0012](0012-production-on-ecs-fargate-and-rds.md)). The code base uses synchronous SQLAlchemy sessions; the connection to a phone is asynchronous.

## Decision

1. **WebSocket plus REST.** REST is the source of truth (history, sending, read marks, lists, settings). A WebSocket (`/api/v1/chat/ws`, JSON frames, protocol version 1) only carries live events; the app works without it by reading the list when it comes to the foreground. gRPC and server-sent events were considered and not chosen: a second server stack and HTTP/2 end to end, or a one-way channel, for no gain.
2. **PostgreSQL `LISTEN/NOTIFY` between processes, no Redis.** After a message is stored, the same transaction runs `NOTIFY chat_events` with **ids only**. Every API process keeps one dedicated connection that listens, and delivers the event to the sockets it holds. PostgreSQL stays the only infrastructure ([ADR-0002](0002-postgresql-as-the-only-database.md)). A rolled-back transaction announces nothing. Events missed while a listener reconnects are not replayed: the app catches up through the REST list after it reconnects.
3. **Synchronous database work from asynchronous handlers.** Handlers are async; database work runs in the thread pool (`run_in_threadpool`) with short sessions. The spike (`backend/tests/test_chat_hub.py`) shows that four queries sleeping 0.6 s each do not stop the event loop, that a message announced by one process reaches a socket held by another, that the listener reconnects after its connection is killed, and that a rolled-back transaction is silent. No asynchronous SQLAlchemy layer is needed.
4. **Push without shared memory: a delayed outbox with acknowledgements in the database.** No process can see another's sockets, so the sender never asks "is the recipient connected?". It writes an outbox row with `send_after = now + CHAT_PUSH_DELAY_SECONDS`. The process that delivers the frame records the person's `delivered_seq` (and `last_read_seq` when read); the worker cancels a due row when the recipient has acknowledged the message, and merges waiting rows of one conversation into one push. The push text is fixed and generic, with no message text.
5. **Messages are between people.** The church model has one account type, so the design's "work host" and "freelancer" become the two **sides of a conversation**: the *starter* (a SEARCHER or above who found a provider) and the *provider* (open, not revoked, PROVIDER or above, the same rule as Reveal and rating). One conversation per pair. Only the provider side may block; both may mute and report. Sides in the protocol are `starter` and `provider`.
6. **Authentication** is the normal access token, sent in the first frame (never in the address); the person is read from the database as for every request (ADR-0017). A socket that is already open is ended by three means: the access token's expiry closes it with `4401` after at most 15 minutes; every frame the app sends (`ping` every 25 seconds included) re-reads the person, and a revoked or closed person is answered with close code `4403` at once; and an event is delivered to a person only after the receiving process has checked that they are still open (so a revoked person gets no message in the meantime). `Hub.close_person` closes a person's sockets in the process that holds them.
7. **Privacy.** Messages are visible to the two participants and, for a reported conversation, to the OWNER through a logged access. Logs never contain a message, a token or a number. Deleting an account anonymises that side; the other keeps the history. The privacy page and the store data-safety answers are updated before chat is released.

## Consequences

- One more long-lived database connection per API process (the listener), and one worker job (the push sender).
- A worst-case delay of `CHAT_PUSH_DELAY_SECONDS` (3 s) before a push for an offline person; nothing depends on in-memory state, so it is correct with one process or ten and survives restarts.
- `NOTIFY` payloads are limited to about 8 000 bytes: ids only, by design.
- A load balancer in front of several processes needs an idle timeout above 60 seconds (the app pings every 25 seconds and the server closes a socket that is silent for 70 seconds; see the runbook, "The chat socket").
- Chat sends no push until a Firebase project exists (`PUSH_ENABLED`); the rest works without it.
- On the development host the first database connection of a process can take about 11 seconds; the chat tests warm it first.
