# Skills frontend

React 18 + TypeScript + Vite. One app with four role-based portals (freelancer, work host, organisation, admin). See `docs/specification/06-frontend.md`, including the responsive web design requirements: every page works on phone, tablet and desktop.

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api and /health to VITE_API_PROXY (default http://localhost:8000)
npm run lint && npm run format:check && npm run typecheck && npm test
```

On the Pi (no Node needed): `make pi-test-web`, `make pi-format-web`, and `make pi-lock-web` after changing dependencies.

## Layout of `src/`

| Folder              | Contents                                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `api/`              | `http.ts` (fetch wrapper: bearer token, one shared silent refresh on 401, `ApiError`), `auth.ts` (auth endpoints), `types.ts`               |
| `auth/`             | `tokenStore.ts` (access token in memory, refresh token in `sessionStorage`), `AuthContext.tsx`, `guards.tsx` (`RequireAuth`, `RequireRole`) |
| `portals/`          | `config.ts`: each portal's path, role name and navigation. New portal pages are added here and in `App.tsx`                                 |
| `shell/`            | `PublicLayout` (visitors) and `AppShell` (signed in: top bar, navigation drawer below 1024 px, side column from 1024 px)                    |
| `pages/`            | Landing, login, register, forgot and reset password, dashboard, not found                                                                   |
| `shared/`           | form components (`ui.tsx`), zod schemas (`validation.ts`), error messages (`errors.ts`)                                                     |
| `i18n/`             | all user-visible text, so more languages can be added (Q9)                                                                                  |
| `styles/global.css` | design tokens, light and dark themes, mobile-first layout, breakpoints 640 px and 1024 px                                                   |

## Rules for new pages

- Mobile first: write the small-screen layout, then add `@media (min-width: 640px)` and `(min-width: 1024px)` rules. Never fix a pixel width on a container.
- Interactive elements are at least 44 px high and wide; nothing depends on hover.
- Every input has a visible label; errors are linked with `aria-describedby`.
- Text goes through `t()` in `src/i18n`, not into the components.
- Every list and page has loading, empty and error states.
- Tests never contain real or fixed passwords; use `PASSWORD` from `src/testUtils.tsx`.

## Known gaps (planned)

- The API client is written by hand for the auth endpoints. Generating types from the backend OpenAPI schema (`openapi.json` from `ci-backend`) is planned before the portal pages are added.
- Browser tests at the five reference viewports (Playwright) are added once there are enough pages to check.
