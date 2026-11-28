### Background

ADR-0005 says the web app uses "an API client generated from the backend OpenAPI schema". It does not: the types in `frontend/src/api/types.ts` (61 types) and the calls in `frontend/src/api/person.ts` (56 functions), `auth.ts`, `freelancer.ts` and the other `api/*.ts` files are written by hand. Nothing checks them against the backend, so a field added, renamed or removed on the server is only noticed when a screen breaks. Story S100 showed this: `must_change_password` had to be added by hand to `PersonMe` and to the test helpers.

The backend already writes the contract to `docs/openapi.json`, and CI fails when that file is out of date (`make openapi`, `app/openapi_export.py`).

### Feature Criteria

1. The TypeScript types of every request and response body are **generated from `docs/openapi.json`** (for example with `openapi-typescript`, pinned to an exact version), into one generated file under `frontend/src/api/` that is committed and never edited by hand.
2. A command regenerates it (`npm run api:types`, and a `make` target next to `make openapi`).
3. CI fails when the generated file does not match `docs/openapi.json`, the same way it does for `docs/openapi.json` itself.
4. The hand-written types in `api/types.ts` are replaced by the generated ones (directly or as named aliases, e.g. `export type PersonMe = components['schemas']['PersonMeResponse']`). The call functions in `api/*.ts` keep their names and signatures, so the pages do not change beyond imports.
5. The request helper (`api/http.ts`) stays as it is: no new runtime dependency is required (types only). A generated runtime client is optional and needs a decision in the ADR if added.
6. Any mismatch the generation exposes (a field the screens expect that the API does not send, or the reverse) is fixed or listed in the PR.

### Repositories affected:

Frontend: Yes

Backend: No (only reads `docs/openapi.json`)

### Scope

Types and the build step only. No change to what any screen shows or does.

### Test Criteria

- `npm run typecheck`, `npm run lint` and `npm test` pass with the generated types.
- A check (script or test) proves the generated file is up to date with `docs/openapi.json`.
- Changing a response field in a throwaway copy of `docs/openapi.json` makes the type check fail where a screen uses it (demonstrated once, not committed).

### Definition of Done

The test suite passes, CI has the new up-to-date check, and ADR-0005 is true again (or the ADR is updated to say exactly what is generated).
