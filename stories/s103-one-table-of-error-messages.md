### Background

The web app turns the server's error codes into words in 14 places: the shared `errorMessage` in `frontend/src/shared/errors.ts`, and 13 pages that each have their own small `problem(error)` function (for example `pages/person/owner/Churches.tsx` maps `church_name_taken`, `owner_church`, `state_changed`, `successor_not_member`, and more). The same codes are handled in several of them (`state_changed`, `successor_not_member`, `invalid_choice`), sometimes with different wording, and `shared/errors.ts` itself is the least-tested file in the app (65% of its lines).

### Feature Criteria

1. One table, in `shared/errors.ts`, maps every error code the API can return (the list at the end of `docs/specification/04-api.md`) to a string key in `i18n/index.ts`.
2. Where a page really needs different words for the same code (because the context differs), the table allows a per-screen override in one place, e.g. `errorMessage(error, { successor_not_member: 'owner.error.notMember' })`, instead of a separate function.
3. The 13 local `problem()` functions are removed; each page calls `errorMessage`, with an override only where needed.
4. A code the table does not know still falls back to the generic message, as today.
5. Wording a person sees does not change, unless two pages used different words for the same situation; those are listed in the PR and unified.

### Repositories affected:

Frontend: Yes

Backend: No

### Scope

Error wording and its tests only.

### Test Criteria

- Existing page tests pass (they check the words people see).
- A test checks that every error code listed in `docs/specification/04-api.md` has an entry in the table, so a new code cannot ship without words.
- `shared/errors.ts` reaches at least 90% line coverage.

### Definition of Done

The test suite passes, and there is one place to change an error message.
