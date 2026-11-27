### Background

A scan of `backend/app` on `main` (2026-11-27) found four definitions, about 30 lines, that nothing calls. Every module is imported, every setting is read, and every dependency is used. Only the items below are dead.

| Item | Where | How it became dead |
|---|---|---|
| `DEMO_DOMAIN = "example.com"` | `backend/app/cli.py:42` | It built the older demo accounts' emails. Commit `f9ef18e` (2026-11-15, the demo data over the church model) removed both uses and left the constant. |
| `_successor_required()` | `backend/app/services/group_requests.py:56` | Called twice when a leader asked to start a group. Commit `a746a95` (#138) moved that check into the succession code, which raises the same error itself, and left the helper. |
| `other_side()` | `backend/app/chat/rules.py:43` | Written in `fc2bdfc` (S8.2, chat) and never called, even in that commit. |
| `searchable_providers()` | `backend/app/reports/definitions.py:59` | Written in `aaa863d` (the reports over people) and never called; that commit wrote the same rule as the SQL `searchable` clause of the report instead. |

### Feature Criteria

1. The four definitions above are removed. Nothing else changes: removing them leaves no import unused.
2. **The error code `successor_required` stays.** Six other places raise it (`ownership.py`, `revocation.py`, `succession.py`), and both apps show words for it. Only the unused helper that built it goes.
3. **The SQL column `searchable_providers` stays.** It appears in the report query in `definitions.py` (around lines 364 and 391). It is the name of a report column, not a call of the function.
4. **Kept on purpose**, though only tests use them. They are test hooks that reset state between tests and check internal limits, such as old entries being cleared:
   - `SlidingWindowLimiter.reset()` (`services/rate_limit.py`)
   - `DownloadLimiter.reset()` and `DownloadLimiter.tracked_people()` (`services/downloads.py`)
   - `Hub.connected_people()` (`chat/hub.py`)
5. **Not dead, and not part of this story:**
   - `KINDS` in `services/notifications.py`, the list of notification types. Only five test assertions read it. Whether to remove it, or to give it a purpose (a test that every type has wording in both apps), is a separate decision.
   - The OWNER's chat-moderation endpoints (`/owner/chat-reports…`). They are a specified feature (S8.4) whose screen is not built yet.
6. Nothing the API does changes. `docs/openapi.json` is unchanged (`make openapi` confirms it).

### How the list was verified (2026-11-27, on `main`)

- **Removed in a throwaway copy of `backend/`.** Ruff, `ruff format --check`, mypy and the full test suite passed: 1,399 passed and 2 skipped. The extra skip, compared with `main`, was `test_app_config.py:103`, which compares the frontend's terminology files and skips when there is no `frontend/` folder beside the copy. It touches none of the four items.
- **A search of every tracked file** (backend, scripts, CI workflows, Docker files, Makefile, docs, both apps) finds each name only at its definition. The other matches are a local variable `other_side` in `tests/test_chat_moderation.py` and the SQL column above.
- **Dynamic access was ruled out.** No `getattr`, `globals()`, `vars()`, `importlib`, `__import__`, `eval`, `exec`, `import *` or `__all__` in the backend can reach them: each `getattr` uses a fixed attribute name, and `__all__` exists only in `app/models/__init__.py`.
- **There are no outside callers.** The backend is not published as a package. The only other Python in the repository is in `scripts/`, which loads its own helper files only.
- **The history** (`git log -S`) shows when each item lost its last caller, as in the table above.

### Repositories affected:

Frontend: No

Backend: Yes

### Scope

Removal only, no new behaviour. Do not perform any git push commands.

### Test Criteria

- `ruff check`, `ruff format --check`, `mypy app` and the full backend test suite pass.
- `make openapi` reports `docs/openapi.json` up to date.

### Definition of Done

The test suite passes, and a search for the four names in `backend/app` finds nothing except the SQL column `searchable_providers`.
