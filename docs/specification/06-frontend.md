# 06 Frontend

Decision record: [ADR-0005](../adr/0005-react-typescript-frontend.md). One React app, role-based portals sharing components. API access only through the generated client.

## Portals and pages

### Public
Landing, register (choose user type), forgot and reset password, and three login pages, each tied to one kind of account (the page, not a dropdown, decides the `user_type` sent to the API):

| Page | Address | For |
|---|---|---|
| Log in | `/login` and `/login/workhost` | Freelancers and work hosts. Two links at the top of the form switch between them. |
| Organisation log in | `/login/organisation` | Organisations only. States that a new organisation needs admin approval. Links to organisation sign-up. |
| Admin log in | `/login/admin` | Admins only. No sign-up link (admins are created by operators). |

The login pages do not link to each other except the Freelancer / Work host switch; the organisation and admin addresses are shared directly.

A visitor who opens a protected address is sent to the login page that fits it (for example `/admin/reports` leads to the admin login). Old links of the form `/login?type=organisation` are redirected.

### Freelancer portal
Dashboard; profile; rate and currency; labels (skills with levels, languages, timings, nativity); unavailability calendar; my ratings; my organisation vouches.

### Work host portal
Dashboard; profile and available days; freelancer search with filters and sorting; freelancer detail; rate a freelancer; my ratings given.

### Organisation portal
Dashboard; profile; vouched freelancers (add, revoke, status); organisation reports.

### Admin portal
Organisation approvals (waiting, approved and rejected lists; approve or reject); label management (add, rename, deactivate or reactivate, by kind); report pages for all reports (date range plus each report's own filters, table on screen, CSV download); report history (kept runs with CSV and HTML downloads, and running and keeping a report for chosen dates); and schedule editing. Charts are not built yet; tables and CSV cover the reports.

## Installation terminology

Screen text refers to the three kinds of people through tokens such as `{organisation}`,
`{Workhosts}` and `{a_freelancer}` (see `src/terminology/terms.ts`). The words and the web-address
segments come from the active profile in `src/terminology/profiles.json` (key/value pairs, one block
per profile). The profile is chosen per installation: the web server serves `/config.json` from its
`TERMINOLOGY_PROFILE` setting and the app reads it before it starts (development uses
`VITE_TERMINOLOGY_PROFILE`). An unknown name falls back to `default`. Portal, login and register
addresses are built from the profile (`/church`, `/login/church`, `/register/church`), while API
paths, `user_type` values, report files and emails are unchanged.

## UI requirements

- Responsive web design (RWD) on every page, see the next section.
- Accessible: keyboard navigation, labels on inputs, sufficient contrast (WCAG 2.1 AA target).
- Form validation with zod mirroring API rules; show API error messages clearly.
- Access token kept in memory; silent refresh using the refresh token; log out on refresh failure.
- Loading, empty and error states for every list and page.
- Strings kept in a translation file so more languages can be added (Q9).

## Responsive web design

Every page, in every portal, works on phones, tablets and desktops. This is a release 1 requirement, not a later polish step.

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
- **Filters** on freelancer search: a slide-in panel on mobile and tablet, a side panel on desktop.
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
