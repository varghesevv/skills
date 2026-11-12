# 06 Frontend

The Android app is specified in [docs/android/](../android/plan.md); its screens mirror the portals below ([parity table](../android/parity.md)).

Decision record: [ADR-0005](../adr/0005-react-typescript-frontend.md). One React app; the screens shown depend on the person's status and share components. API access only through the generated client.

## Screens by status

One React app and one login. After login the app reads `GET /me` and shows the screens that the person's **status** allows (ADR-0017); there are no separate portals and no login page per kind of account. A higher status sees everything the lower ones see, plus its own screens. Words come from the terminology profile (below).

### Public
Landing, log in, forgot and reset password, and the **sign-up wizard**: details (name, email, mobile number, password), choose a church, choose a home group (each with its leader's name), and choose to apply as a searcher or a provider. A group invitation link (`/join/<token>`) skips the church and group steps. A vouch link (`/vouch/<token>`) asks the visitor to log in first, then shows who is asking and lets an admitted person vouch.

### Applicant (PENDING)
Application status (church, home group, who the leader is, what they applied for), the vouches received, the person's own vouch link to share, change of church, group or choice, and leave (close the account). Nothing else.

### Revoked
A single page saying the account has no access, with log out and password reset.

### Searcher (SEARCHER and above)
Dashboard; profile; provider search with filters and sorting; provider detail; rate a provider; my ratings given; vouch for applicants through links; share my vouch link when applying to provide; request to start a home group; move requests that concern me; notifications.

### Provider (PROVIDER and above)
Everything a searcher has, plus rate and currency; labels (skills with levels, languages, timings, nativity); unavailability calendar; my ratings received; who vouched for me.

### Verifier (VERIFIER and above, within scope)
Applicants with their vouches (most-vouched first) with admit and decline; members; the revoked list with revoke and reinstate; people flagged for re-checking, shown prominently, with re-confirm; the group's invitation link; move agreements; the step-down and succession screens; the leader's view of a person, including the mobile number (privacy rules in [07](07-non-functional.md)).

### ADMIN
Everything a verifier has for every group in the church, plus: group requests (approve, decline), appoint or replace a group leader, move members, the church's people and revoked list, and church reports.

### OWNER (web only)
Everything an ADMIN has for every church, plus: churches (create by inviting an ADMIN, close), invitations, replace a church's ADMIN, label management (add, rename, deactivate or reactivate, by kind), all reports (date range plus each report's own filters, table on screen, CSV download), report history and schedules, and the OWNER handover. Charts are not built yet; tables and CSV cover the reports.

## Installation terminology

Screen text refers to the kinds of people and the structure through tokens such as `{church}`, `{home_group}`, `{Searchers}`, `{a_provider}`, `{verifier}`, `{admin}` and `{owner}` (see `src/terminology/terms.ts`). The words and the web-address
segments come from the active profile in `src/terminology/profiles.json` (key/value pairs, one block
per profile). The profile is chosen per installation: the web server serves `/config.json` from its
`TERMINOLOGY_PROFILE` setting and the app reads it before it starts (development uses
`VITE_TERMINOLOGY_PROFILE`). An unknown name falls back to `default`. Web addresses that carry a word (for example the provider pages) are built from the profile, while API
paths, status values, report files and emails never change with the words. The keys for searcher, provider, verifier, admin, owner, church and home group are added in S2.9; the backend and web copies of the profiles stay equal.

## UI requirements

- Responsive web design (RWD) on every page, see the next section.
- Accessible: keyboard navigation, labels on inputs, sufficient contrast (WCAG 2.1 AA target).
- Form validation with zod mirroring API rules; show API error messages clearly.
- The screens shown depend on the status from `GET /me`, which is read again on every start and after every `403`. The access token is kept in memory; silent refresh using the refresh token; log out on refresh failure.
- Loading, empty and error states for every list and page.
- Strings kept in a translation file so more languages can be added (Q9).

## Responsive web design

Every page, for every status, works on phones, tablets and desktops. This is a release 1 requirement, not a later polish step.

### Approach
- Mobile first: base styles are for the smallest screen; larger screens add rules with `min-width` media queries.
- Breakpoints (CSS custom properties, one definition shared by all components):

| Name | Width | Typical device | Layout |
|---|---|---|---|
| mobile | below 640 px | phones | single column, navigation behind a menu button, full-width controls |
| tablet | 640 to 1023 px | tablets, large phones in landscape | up to two columns, collapsible side navigation |
| desktop | 1024 px and above | laptops, desktops | persistent side navigation, multi-column content, content width capped at about 1200 px |

- Fluid layout with CSS grid and flexbox; relative units (`rem`, `%`, `fr`); no fixed pixel widths for containers.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`; page zoom is never disabled.
- Layout adapts to the viewport and to orientation changes, not to the device type.

### Components
- **Navigation:** a top bar with a menu button on mobile, a collapsible side menu on tablet, a persistent side menu on desktop.
- **Tables** (search results, report sections, run history): on mobile each row becomes a stacked card or the table scrolls horizontally inside its own container; the page itself never scrolls sideways. Key columns stay visible. Report pages keep all columns reachable on every size.
- **Forms:** single column on mobile, two columns where it helps on wider screens; labels always visible; correct `type`, `inputmode` and `autocomplete` values so phones show the right keyboard.
- **Mobile number:** shown as a greyed placeholder with a **Reveal** button on searcher search results and the provider detail page. Reveal calls the server; on a touch device (`hover: none` and `pointer: coarse`) it then opens the dialler, otherwise it shows the number as a `tel:` link. The number lives only in the component state. A refused request (limit reached) shows the wait time and the button stays available.
- **Filters** on provider search: a slide-in panel on mobile and tablet, a side panel on desktop.
- **Calendar** (unavailability): month view on tablet and desktop, list view on mobile.
- **Dialogs and menus:** full-screen sheets on mobile, centred dialogs on larger screens; focus is trapped and returned on close.
- **Images and charts:** scale to the container; charts redraw on resize.

### Usability on touch devices
- Touch targets at least 44 by 44 CSS pixels with space between them.
- No feature depends on hover; every hover action has a tap or keyboard equivalent.
- Body text at least 16 px (also prevents iOS zoom on focus); text can be enlarged to 200 percent without loss of content or function.
- Respect `prefers-reduced-motion` and `prefers-color-scheme` where supported.
- Safe-area insets are respected on devices with notches.

### Browsers and test sizes
- Supported: the latest two versions of Chrome, Safari (including iOS), Firefox and Edge, plus Chrome on Android.
- Reference viewports used in review and tests: 360 x 640 (small phone), 390 x 844 (phone), 768 x 1024 (tablet portrait), 1024 x 768 (tablet landscape), 1440 x 900 (desktop).

### Acceptance criteria
1. No horizontal page scrolling at any width from 320 px up.
2. Every function in the portals can be completed at 360 px width using touch only.
3. Layout changes at the breakpoints above, with no overlapping or clipped content.
4. Each page is checked at all five reference viewports, with automated browser tests (Playwright screenshots and an overflow check) for the shell, login, search, a form page and a report page. They live in `frontend/e2e` and run in CI as the `responsive` job.
5. Pages meet the WCAG 2.1 AA reflow and target-size expectations.
