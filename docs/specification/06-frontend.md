# 06 Frontend

The Android app is specified in [docs/android/](../android/plan.md); its screens mirror the portals below ([parity table](../android/parity.md)).

Decision record: [ADR-0005](../adr/0005-react-typescript-frontend.md). One React app; the screens shown depend on the person's status and share components. API access only through the generated client.

## Screens by status

**Transition.** The older portals and their login and register pages stay until slice S5.6 removes them (decision D-20). Until then the screens of this section that exist live at their own addresses next to them: sign in at `/sign-in`, joining at `/sign-up`, an invitation link at `/join/<token>`, the home of a person at `/member`, the vouches a member gave at `/member/vouches`, notifications at `/member/notifications`, starting a home group at `/member/group-requests` and moving to another one at `/member/moves` (any admitted member), a vouch link at `/vouch/<token>`, and for leaders the applicants at `/member/applicants`, the members at `/member/members`, people to re-check at `/member/flagged`, the revoked at `/member/revoked`, the groups of the church at `/member/groups` (ADMIN and OWNER), a leader's own group at `/member/group` and one person at `/member/people/<id>`. S5.6 moves them to `/login`, `/signup` and `/` and removes the older pages. A person who opens an address of an older portal is sent to `/member`, and an older account that opens `/member` is sent to its own portal.

One React app and one login. After login the app reads `GET /me` and shows the screens that the person's **status** allows (ADR-0017); there are no separate portals and no login page per kind of account. A higher status sees everything the lower ones see, plus its own screens. Words come from the terminology profile (below).

### Public
Landing, log in, forgot and reset password, and the **sign-up wizard**: details (name, email, mobile number, password), choose a church, choose a home group (each with its leader's name), and choose to apply as a searcher or a provider. A group invitation link (`/join/<token>`) skips the church and group steps. An invitation to be an ADMIN (`/invite/<token>`, built with the OWNER's screens in S4.9) shows the church and the domain of the invited address, and asks for the name, mobile number, password and the name of the first home group; the email address is the one invited. A vouch link (`/vouch/<token>`) asks the visitor to sign in first and brings them back to it, then shows who is asking (name, church, group, what for; never a number) and lets an admitted person vouch. An applicant who opens it is told that only admitted people can vouch, without asking the server. Notifications are polled every 60 seconds while the app is open; a revoked person does not ask for them. The vouch token is sent in the body of the API request (`POST /vouch-links/lookup` and `/vouch`), never in an API path or query string, and never in a client cache key; a client (the mobile app too) does the same.

### Applicant (PENDING)
Application status (church, home group, who the leader is, what they applied for), the vouches received, the person's own vouch link to share (shown once when made, with a copy button and the phone's share sheet where there is one; making a new one ends the old), change of church, group or choice, and leave (close the account, with the password asked again), and notifications in the top bar. Nothing else. Built in S2.7 and S3.4.

### Revoked
A single page saying the account has no access, with log out and password reset.

### Searcher (SEARCHER and above)
Dashboard; profile; provider search with filters and sorting; provider detail; rate a provider; my ratings given; vouch for applicants through links; ask to start a home group (`/member/group-requests`, for every admitted member; the approval is in the ADMIN section and the whole screen is described under the Verifier section, S4.7b); the vouches I gave, with withdraw until the person is admitted (`/member/vouches`); offer my skills (a button on the home of a searcher; after it the home shows the request, the vouches so far and the person's own vouch link, and they go on searching); move requests that concern me; notifications (list and mark as read, `/member/notifications`; an applicant has them too, a revoked person does not).

### Provider (PROVIDER and above)
Everything a searcher has, plus rate and currency; labels (skills with levels, languages, timings, nativity); unavailability calendar; my ratings received; who vouched for me.

### Verifier (VERIFIER and above, within scope)
The top bar shows Applicants, Members, To re-check, Revoked, My group and Moves to a leader only, and the home groups to an ADMIN or the OWNER. Applicants with their vouches (most-vouched first, every voucher and whether it counts) with admit as a searcher or a provider (the server decides whether a provider may be admitted, which needs a vouch from someone besides the leader; both the applicants list and one person's page follow the server's `can_admit_as_provider`; the server's refusals have their own messages) and decline (which asks first, because it cannot be undone), paged by 50; members with a filter by status; one person's page with the mobile number, vouches, history and chain of trust (privacy rules in [07](07-non-functional.md): the page asks the server once and keeps the answer in its own state, not in the query cache, because every view is recorded; after an admission it updates itself from the answer); lists carry no numbers. A member who asks to offer their skills is listed among the applicants with a label, only the provider admission is offered, and declining ends the request and leaves them a searcher. Built in S3.5 and S3.9b. Built in S4.7a: the revoked list (with the group each was removed from and by whom) and the list of people flagged for re-checking (who set their status), both paged by 50 and without numbers; on one person's page, revoke (which asks first, and is offered for searchers and providers; a VERIFIER is revoked by an ADMIN or the OWNER together with their successor (S4.8b-2) and an ADMIN by the OWNER (S4.9), and the page says so), reinstate of a revoked person into an open group of their church as a searcher or a provider, and re-confirm of a flagged status; the page updates itself from the server's answer and the server's refusals (a higher leader's revocation, already revoked, no flag) have their own messages. Built in S4.7b: starting a home group (`/member/group-requests`, linked from the member's home): any admitted member asks by naming it and sees their own requests with their state; an ADMIN or the OWNER start one at once and, if they lead a group now, choose who leads it from now on (from the members of that group); an ADMIN sees the waiting requests of the church (the OWNER those of every church) and approves or declines each, choosing who leads the requester's current group when the request says they lead one (from that group's members, shown by `requester_group`; Approve waits for the choice unless the requester is alone in the group, which then closes; the server checks membership); each row names its church. The server's refusals (name taken, a request already waiting, decided meanwhile, member gone) have their own messages. The notifications list reads the new kinds in words (a request, its answer, being brought back). Built in S4.8a (ADMIN and OWNER only; others are sent home): the open groups of the church with their leaders, each with a form to choose who leads it from now on (from the other members of that group; the old leader becomes a provider or a searcher, or keeps their status when they are an ADMIN or the OWNER handing on their own group; the server's refusals have their own messages), and on a member's page a form to move them to another open group of the church without the agreements a move by request needs (a leader is not moved: the page says to change the leader first). Built in S4.8b-1: moving between groups by agreement (`/member/moves`, linked from the member's home and from the leader menu): an admitted member picks another open group of the church and asks (which is their own agreement; a leader is told to hand their group on first); every move that concerns the person is listed with who agreed and who is awaited, the leader of the group they leave or the group they join agrees (once) and either leader or the member cancels, and the page says when the last agreement moved the member; the server's refusals have their own messages, and the notifications list reads the move kinds. A leader stops leading when an ADMIN or the OWNER choose a successor on the groups page (S4.8a), or, being the last member of their group, by closing it from their own page (S4.8b-2); it also happens when a leader who starts another group names who leads the old one (S4.7b), when the requester of an approved group is replaced as leader of their old group (S4.7b), and when a VERIFIER is revoked with a successor (S4.8b-2); a leader with members cannot just step down on their own. Built in S4.8b-2: on a VERIFIER's page an ADMIN or the OWNER revoke them together with their successor (chosen from the other members of the group, required when there are any; alone in the group, the group closes with the revocation; the members are loaded with a retry on failure), while a VERIFIER is told that only an ADMIN or the OWNER can, and an ADMIN is still replaced by the OWNER (S4.9); and a leader's own page (`/member/group`) closes their group when they are its last member by joining another open group (it asks first; a VERIFIER chooses to become a provider or a searcher, an ADMIN or the OWNER keep their status; the page then reloads who they are and the outcome is shown once on their home, because a former VERIFIER no longer belongs on the leader pages). The server's refusals have their own messages. Still to come: the OWNER's replacement of an ADMIN (S4.9); the group's invitation link.

### ADMIN
Everything a verifier has for every group in the church, plus: group requests (approve, decline), appoint or replace a group leader, move members, the church's people and revoked list (the Members and Revoked pages, which an ADMIN sees for the whole church), and church reports.

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
