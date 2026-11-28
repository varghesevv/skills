### Background

The older account types (freelancer, work host, organisation, platform admin) were replaced by the church trust model, and the backend no longer has them: `GET /me` only answers `PersonMeResponse` (`user_type: "person"`), and the older `MeResponse` is gone. The web app still carries their traces:

- `frontend/src/api/types.ts`: `UserType = 'freelancer' | 'workhost' | 'organisation' | 'admin'`, the older `Me` type and `AnyMe = Me | PersonMe`.
- `frontend/src/auth/AuthContext.tsx`: checks `user_type !== 'person'` to reject an "account of the older kind", which can no longer exist.
- `frontend/src/api/auth.ts`: `fetchMe()` returns `AnyMe`; `forgotPasswordRequest` still sends `user_type: 'person'`, which the server ignores.
- `frontend/src/testUtils.tsx`: `makeMe()` builds an older freelancer account, and `signedInAs(me = makeMe(), ...)` uses it as its default, in about 20 test files.
- `frontend/src/api/freelancer.ts`: the API module of the **provider** pages. Its endpoints (`/freelancers/me`, `/freelancers/me/unavailability`, ratings) are **still live**, so it is renamed (e.g. `api/provider.ts`), not deleted; its types are renamed from `Freelancer…` to `Provider…` where they are the web app's own names.

### Feature Criteria

1. `UserType`, `Me` and `AnyMe` are removed; `fetchMe()` returns `PersonMe`.
2. The older-account checks in `AuthContext.tsx` are removed. A `GET /me` answer that cannot be read still signs the person out, as any bad answer does.
3. `forgotPasswordRequest` sends only `email`.
4. `makeMe()` is removed from `testUtils.tsx`; `signedInAs()` takes the person's details (a `makePerson()` override) instead, and the tests that used `makeMe()` are updated.
5. `api/freelancer.ts` becomes the provider module, imported by the five places that use it today (`shared/RatingsList.tsx`, `pages/person/provider/ProfilePage.tsx`, `LabelsPage.tsx`, `AvailabilityPage.tsx`, `pages/person/search/SearchPage.tsx`). The API paths do not change.
6. Nothing a person sees changes.

### Repositories affected:

Frontend: Yes

Backend: No (renaming the `/freelancers/...` paths would be a separate API story)

### Scope

Do S105 (generated API types) first if possible: once the types are generated from `docs/openapi.json`, the older ones disappear on their own and this story is smaller.

### Test Criteria

- `npm run typecheck`, `npm run lint` and `npm test` pass.
- A search for `freelancer`, `workhost`, `organisation'` and `user_type` in `frontend/src` finds only the live API paths and the terminology words (`{freelancers}`, `{organisation}`), nothing else.

### Definition of Done

The test suite passes, and the web app has no code for account types that no longer exist.
