# Design system and UI specification

Status: built in one pull request, steps 1 to 5 of section 4 (2026-11-17). Steps 6 and 7 are not built, as the open points of section 5 decide. It changes no data, roles or permissions, so [verification.md](verification.md) is unchanged.

Direction: **Dark Graphite & Warm Stone**, with an **Electric Indigo** call to action and a green for trust. Desktop first in layout, mobile first in CSS. Built for fast scanning and few clicks. The target is WCAG 2.2 AA.

How to read this document: section 0 lists the rules the design must keep, sections 1 and 2 say *what* the look and behaviour are, section 3 shows *how* that fits the code that exists (`frontend/src/styles/global.css`, `shell/PersonLayout.tsx`, `pages/person/search/`), section 4 is the build order and section 5 lists what the owner must decide. Where this document and [06-frontend.md](specification/06-frontend.md) differ, the specification stays in force until a build step changes both in the same pull request.

## 0. Rules the design must keep

These come from the specification and the code. A step that breaks one is wrong, however good it looks.

1. **No field the API lacks.** A search result has the name, nationality, languages, rate, currency, negotiable flag, average rating and count, church and home group (id and name only), skills with levels, timings and nativity. It has **no picture, no leader name, no match score and no number** (FR-P-07, FR-M-06). If a design needs more, change the API and the specification first.
2. **Words come from `t()` and the terminology profile.** No English in components. Kinds of people and the structure are tokens (`{freelancers}`, `{Organisation}`, `{Homegroup}`, see `src/terminology/`), so an installation can name them differently. The words are the active profile that `GET /api/v1/app/config` serves (FR-C-08; the web app reads the same keys from `profiles.json`, and a test keeps the two equal). A label such as the home-group word is never typed into a component. Keys marked *new* below are added to `i18n/index.ts`.
3. **A higher status includes the lower.** Navigation follows one set of status rules (the ones `PersonLayout` has now), never a role switch.
4. **Reveal is sacred** (FR-M-05 to FR-M-07). The number is asked for only on a press, lives in component state, is never cached or prefilled, opens the dialler on a phone, and a `429` shows the wait. Every reveal is logged and limited, so no shortcut key and no automatic reveal. A provider's own card has no Reveal, as now.
5. **State in the URL.** Filters, sort and page stay in `searchParams.ts`, so a refresh, a share and Back work.
6. **Mobile first.** Base CSS is the smallest screen. Wider screens add `min-width` rules at 640px and 1024px, the two values already in `global.css`. Never `max-width`.
7. **Plain CSS and `rem`.** The frontend has no Tailwind and none is added. Sizes are in `rem`, so the browser's text-size setting works. Existing class names stay (`.btn`, `.card`, `.badge`, `.chip`, `.field`), so existing screens restyle by changing tokens, not markup. Outside the token block, `global.css` names no colour except the dialog scrim.

### How the brief maps to Skills

| Brief | In Skills | Why |
|---|---|---|
| Job feed, job card | **Provider results, provider card** | The things searched are providers (FR-S-06) |
| Budget badge | **Rate** (`formatRate`) and the **Negotiable** badge | FR-P-02 |
| Payment verified | **Church and home group line** with a shield icon | Every listed provider is already admitted, so a "Vouched" badge on every card says nothing. The card shows *who stands behind them*. The leader's name joins it once the API sends it (section 5) |
| Find Work / Hire Talent | **Find {freelancers}** (everyone admitted) and a **My services** group (PROVIDER and above) | A grouped menu, not a mode switch. A SEARCHER never sees My services |
| Match percentage | **Skill match**: of the skills searched, how many the provider has | Worked out in the browser from the filter and the result's `skills`. Shown only when skills are filtered with *any* |
| Rate range | Highest rate, currency, negotiable only (FR-S-02) | |
| Timezone overlap | **Available from / until** (FR-S-03) | The app has no timezones |
| Engagement type | **Timing** (FR-S-01) | |
| Apply from the slide-over | **Reveal** and **Rate** on the provider's page | The contact action is the conversion |
| Avatar photo | **Initials** in a circle, hidden from screen readers | No picture exists, and photo upload would bring moderation and privacy cost for no need |

## 1. Visual system

### 1.1 Colour tokens

The design keeps the **token names already in `global.css`** (`--bg`, `--surface`, `--ink`, `--muted`, `--line`, `--accent`, `--accent-hover`, `--accent-ink`, `--danger`, `--danger-bg`, `--success`, `--success-bg`, `--info-bg`, `--focus`) and changes their values. It adds five: `--line-strong`, `--accent-bg`, `--accent-bg-ink` and two shadows, `--shadow-card` and `--shadow-raised`. One muted text colour is used, not two, because a second grey adds a decision on every screen and no value.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F5F3EF` | `#151517` | Page background (warm stone / graphite) |
| `--surface` | `#FFFFFF` | `#1F1F22` | Cards, top bar, panels |
| `--ink` | `#1C1B19` | `#F2F0EC` | Body, headings |
| `--muted` | `#57534E` | `#B0AAA3` | Labels, metadata, hints |
| `--line` | `#D6D3CD` | `#3A3936` | Card and divider lines (decorative only) |
| `--line-strong` | `#8C877F` | `#7C776F` | Edges of inputs, checkboxes, the segmented control |
| `--accent` | `#4338CA` | `#A5B4FC` | Primary button fill, links, selected state |
| `--accent-hover` | `#3730A3` | `#C7D2FE` | Hover and pressed |
| `--accent-ink` | `#FFFFFF` | `#0F0E2A` | Text on `--accent` |
| `--accent-bg` | `#E0E7FF` | `#26254F` | Skill pills, initials circle, the current menu item |
| `--accent-bg-ink` | `#3730A3` | `#C7D2FE` | Text on `--accent-bg` |
| `--success` | `#065F46` | `#6EE7B7` | Trust line and the Negotiable badge (icon and text) |
| `--success-bg` | `#D1FAE5` | `#0F2A22` | Background of those |
| `--danger` | `#B42318` | `#FDA29B` | Errors, revoke |
| `--danger-bg` | `#FEF3F2` | `#3A1512` | Error background (unchanged) |
| `--info-bg` | `#EEF4FF` | `#172447` | Notices (unchanged) |
| `--focus` | `#4338CA` | `#A5B4FC` | Focus ring (same as `--accent`) |
| `--shadow-card` | `0 1px 2px rgb(0 0 0 / .06)` | `none` | A card at rest |
| `--shadow-raised` | `0 6px 20px rgb(0 0 0 / .10)` | `none` | A hovered card and a floating menu |

The teal accent in use today (`#0A6C6C`) is replaced by indigo. Because colour is named only in the token block, the change is that block, checked screen by screen (build step 1).

Contrast, computed with the WCAG 2.2 formula and re-checked on 2026-11-17. Thresholds: text 4.5:1, large text 3:1, UI boundaries and the focus ring 3:1.

| Pair | Light | Dark |
|---|---|---|
| `--ink` on `--bg` / `--surface` | 15.53 / 17.21 | 16.02 / 14.44 |
| `--muted` on `--bg` / `--surface` | 6.88 / 7.63 | 7.92 / 7.14 |
| `--muted` on `--accent-bg` | 6.19 | 6.25 |
| `--ink` on `--accent-bg` | 13.97 | 12.64 |
| `--accent-ink` on `--accent` / `--accent-hover` | 7.90 / 9.93 | 9.43 / 12.61 |
| `--accent` on `--bg` / `--surface` (links, focus ring) | 7.13 / 7.90 | 9.15 / 8.25 |
| `--accent-bg-ink` on `--accent-bg` | 8.06 | 9.64 |
| `--accent` on `--accent-bg` (focus ring on a selected item) | 6.41 | 7.22 |
| `--success` on `--success-bg` | 6.78 | 10.02 |
| `--success` on `--bg` / `--surface` | 6.93 / 7.68 | 11.96 / 10.79 |
| `--danger` on `--surface` / `--danger-bg` | 6.57 / 6.05 | 8.47 / 8.35 |
| `--line-strong` on `--bg` / `--surface` | 3.22 / 3.57 | 4.10 / 3.70 |

`--line` on `--surface` is 1.49 (light) and 1.42 (dark). That is deliberate for a decorative card edge, because the text inside is the content. A control or anything that carries meaning must not rely on `--line` alone (WCAG 1.4.11): controls use `--line-strong`. `--line-strong` on `--accent-bg` is only 2.90, so a control with a `--line-strong` edge sits on `--bg` or `--surface`, never on `--accent-bg`.

Rules:

- **Colour is never the only signal.** The trust line has a shield icon and words. A selected filter has a tick. An error has an icon and text. The current menu item is bold and has `aria-current`.
- **Warm stone canvas, clean card.** Light mode uses a hairline and a soft shadow. Dark mode uses the surface step and no shadow.
- **Dark mode follows `prefers-color-scheme`**, with a manual choice (System, Light, Dark) kept in the browser's `localStorage`. That is a per-browser convenience, not an account setting. A script in `index.html` sets `data-theme` before the first paint, so there is no flash. It reads storage inside `try/catch`, because storage can be blocked. If a Content-Security-Policy is ever added, the script becomes an external file or carries a hash.
- `color-scheme: light dark` stays on `:root`, so native controls, scrollbars and the date picker follow the theme.

### 1.2 Typography

| Role | Face | Notes |
|---|---|---|
| UI and body | **Inter** (variable), then `system-ui` | Clear digits for rates and counts. `font-variant-numeric: tabular-nums` on rates and counts |
| Headings | Inter at 650 weight | One family keeps the payload small |
| Codes (report short codes) | `ui-monospace` | |

Self-host the font as `woff2` from the app's own origin, Latin subset, `font-display: swap`, with a preload for the regular weight. The privacy page promises no third parties, so no font CDN. The app ships no font today. If the added weight (about 100 KB) is too much, keep `system-ui` and change nothing else (section 5).

Sizes are in `rem`. The current body is `1rem/1.55` and stays: 16px stops iOS zooming into inputs and is kinder to readers than a 14px dense body.

| Step | Size / line height | Weight | Use |
|---|---|---|---|
| Display | 1.875rem / 2.25rem | 650 | Landing only |
| H1 | 1.5rem / 2rem | 650 | Page title |
| H2 | 1.25rem / 1.75rem | 600 | Section, panel title |
| H3 | 1.125rem / 1.5rem | 600 | Card title (the size `.result h2` has now) |
| Body | 1rem / 1.55 | 400 | Everything, forms included |
| Small | 0.875rem / 1.25rem | 400 | Metadata in a card |
| Caption | 0.75rem / 1rem | 500 | Pills and badges, never smaller |

### 1.3 Space, shape, motion

- Space scale in `rem`: 0.25, 0.5, 0.75, 1, 1.5, 2, 3. Card padding 1rem on mobile, 1.25rem from 640px.
- Radius: 0.5rem controls, `var(--radius)` (0.75rem, as now) cards, 999px pills.
- Elevation: only through `--shadow-card` and `--shadow-raised`, so a component names no shadow colour. Both are `none` in dark mode, where a hover changes the border to `--line-strong` instead.
- Motion: 120ms for hover, 200ms for panels (the filter panel already uses 0.2s), ease-out. Under `prefers-reduced-motion: reduce`: no transforms and no transitions.
- Targets: at least 2.75rem (44px) for every control, as `.btn` has now. Do not make a menu button or the notifications link smaller.
- Focus: a 3px `--focus` outline with a 2px offset on every interactive element, as `global.css` has now. Never removed for pointer users.

## 2. Layout and interaction

### 2.1 Breakpoints

| Name | Width | Layout |
|---|---|---|
| Mobile | below 640px | One column. Navigation behind one **Menu** button. Filters in the existing right-hand panel with a **Show results** button. One card per row |
| Tablet | 640–1023px | The top bar holds the primary links. Cards in two columns. Filters still in the panel |
| Desktop | 1024px and up | The filter column is permanent beside the results. Two or three card columns. Content capped at about 75rem |

These are the breakpoints in [06-frontend.md](specification/06-frontend.md). Only the card grid is new.

### 2.2 Navigation

`PersonLayout.tsx` makes six status checks inline and can show well over a dozen links in one wrapping bar. A leader on a phone gets several lines of links. The redesign keeps the same rules and organises the output.

**One function holds the rules.** `navFor(person, unread)` returns groups. The layout renders them and tests call it directly. It replaces the inline booleans.

| Group | Who | Links (existing routes) |
|---|---|---|
| Find | SEARCHER and above | Find {freelancers}, Ratings I gave |
| My services | PROVIDER and above | Profile, Skills and labels, Availability, My ratings |
| Church | VERIFIER and above | Applicants, Members, To re-check, Revoked, My group, Invite to my group (only if they lead one), Moves |
| Administration | ADMIN and OWNER | Groups, Reports, Handover |
| Owner | OWNER | Views, Labels, Churches |
| Account | everyone with an account | Notifications (with the unread count), My account, Android app, Privacy, Theme, Log out |

A revoked person gets only the revoked page, Privacy and Log out. An applicant gets Notifications, My account and Log out.

```
Tablet and desktop
[Skills]  Find providers · Ratings I gave · [My services ▾] · [Church ▾] · [Admin ▾]    [name…] [Notifications 3] [Account ▾]

Mobile
[Skills]                                                                  [Notifications 3] [☰ Menu]
   Menu panel: every group as a heading with its links, then Account, theme and Log out
```

- **Sticky** from 640px up, as now. On a phone the bar scrolls away today because a leader's links used to fill the screen. With groups behind one button that reason goes, so the bar may become sticky on phones too. Build step 2 decides from the Playwright screenshots.
- **Group menus are disclosure buttons**, not `role="menu"`: a `button` with `aria-expanded` and `aria-controls` that shows a list of links. Esc closes it and returns focus to the button, and focus leaving the group closes it. This works with a keyboard and a screen reader without custom arrow-key code.
- **No Search / My services toggle.** It suggests two modes, but a provider uses both at once, a leader uses a third set, and no existing route is mode-specific. A grouped menu reaches the same pages in the same number of clicks.
- **Global search** is a name field in the bar that goes to `/member/search?name=…`, where the existing name search and chip already work. A suggestion list is a later step (section 4, step 6), because it needs the labels loaded on every page.
- **Notifications** stay a page (`/member/notifications`) with the unread count in the link text, as now. The 60-second poll is unchanged. A pop-up panel is not built: it needs focus handling and a second copy of the list for little gain.
- The email address in the bar (`.topbar-email`) moves into the Account menu.
- **The skip link stays the first tab stop.**

**No bottom tab bar.** Up to nearly twenty destinations by status do not fit four tabs, and the most used one (search) is one tap from Menu. The Android app has its own native navigation, so there is no parity reason. See section 5 if the owner disagrees.

### 2.3 Search and filters

What exists: a filter panel (a right-hand drawer to 1023px, a column from 1024px), a name search, removable chips (`activeFilters.ts`), a sort select (**newest**, **best rated**, **lowest rate**), pages of 12 and a result count. The filters are a form with a **Show results** button.

Changes:

- **Apply as you change, on desktop.** From 1024px the filters apply when a control changes: at once for selects, checkboxes and switches, after 400ms for typed text and numbers. A new request replaces the old one. The old results stay visible, dimmed, until the new ones arrive (the query already keeps the previous data), and the result count is a polite live region. On mobile and tablet the panel keeps **Show results**, because applying while the panel covers the results shows the person nothing.
- **The filters stay the ones in the code:** skills with any / all and level, language, timing, nativity, highest rate with currency, negotiable only, available from and until, church, home group, minimum average rating (a select of 5 to 9) and the name. The rate stays a number field. A slider alone is hard with a keyboard or a screen reader, and a slider plus a number is two controls for one value.
- **Sort has no "Best match".** The API sorts by rating, rate and newest only (FR-S-05). Skill match is shown on the card but is not a sort until the API has one.
- **Chips** exist already: keep their remove buttons (`search.chip.remove`) and "Clear all filters". The mobile Filters button shows the count (`search.filtersActive` has it).
- **An empty result** names a filter to relax, with a one-click removal beside the existing `search.none` text.
- **Group the filters** in the panel under the existing `<details class="filter-group">`: **Skills**, **Rate and time**, **Where**. The first is open by default.

### 2.4 Results

- A CSS grid: one column on mobile, `repeat(auto-fill, minmax(18rem, 1fr))` from 640px, 1rem gap. All cards are the same size. There is no "featured" card, because the default sort is newest and there is no rank to feature.
- **Pagination stays** (the existing `Pager`, 12 per page, the page in the URL). Load more and infinite scroll are not used: a page number is shareable, keeps its place on Back and does not trap keyboard users.
- Loading uses skeleton cards of the same height, so nothing shifts. `QueryBoundary` keeps the error and empty states.

**Card hierarchy**, top to bottom, built only from `SearchResult`:

1. **Name**, the link to the provider's page (`/member/providers/:id`, with the search in router state, as now), after an initials circle.
2. **Rate** with the **Negotiable** badge (`formatRate`, as now).
3. **Rating**: `★ 8.6 (12)` or the existing "no ratings" text.
4. **Trust line** with a shield icon: `{church} · {home group}`. This restyles the line the card has today. The leader's name joins it when the API sends it.
5. **Skill pills** with the level, at most four, then "+3 more". When skills are searched with *any*, one line: "3 of 4 searched skills". The text is the signal; a small meter beside it, if drawn, is `aria-hidden`.
6. **Footer**: nationality and languages in small text (as now) and the existing **Reveal** control, absent on a person's own card.

**The whole card is clickable, done honestly.** The name is a real link. A CSS rule makes the link's `::after` cover the card (the stretched-link pattern), and Reveal sits above it. A real link works with open in a new tab, middle click and screen readers, which a hidden cover button does not. A card is an `<li>` in the results list, as now.

### 2.5 The provider's page

`/member/providers/:id` stays a full page, as built in S5.5a. It already holds the rating form, the ratings list, unavailability and Reveal, and it can be linked to, with a working Back.

A **slide-over** (a panel over the results, with next and previous) is a later, optional step (section 4, step 7). It would give a second way into the same content and a modal to keep accessible, for a gain only to someone looking at many providers in a row. If it is built:

- The page route stays the address. The panel shows the same component, with `?provider=<id>` on the results page, so Back closes it.
- It is a `role="dialog"` with `aria-modal`, a label, a focus trap, Esc to close and focus returned to the card. On mobile it is a full-height sheet.
- Next and previous are buttons, not single-key shortcuts.
- Reveal and Rate behave exactly as on the page.

### 2.6 Rules for every screen

1. **The first screen after sign-in stays the member home** (`/member`), because what it shows depends on status (applicant, searcher, provider, leader). It gains a "Find {freelancers}" tile first for a SEARCHER and above.
2. No full-page reload for filtering or sorting.
3. Every filter, sort and page is in the URL. The design does not keep the last search in the browser, because a name typed into a search is personal data (the access-log rule, ADR-0011).
4. **Keyboard.** Every action works with Tab, Enter and Esc. The one shortcut is `/` to focus the name field, active only when no field has focus, and it comes last (step 6). No single-letter shortcut for an action (WCAG 2.1.4), and none for Reveal.
5. Destructive or irreversible actions (revoke, leave) keep the existing `Confirm` dialog.
6. Every list and page keeps its loading, empty and error states (06-frontend.md, UI requirements).

## 3. Components

### 3.1 Token block

Replace the two blocks at the top of `global.css`, keeping the names. The third block is the manual theme.

```css
:root {
  color-scheme: light dark;
  --bg: #f5f3ef;          --surface: #ffffff;
  --ink: #1c1b19;         --muted: #57534e;
  --line: #d6d3cd;        --line-strong: #8c877f;
  --accent: #4338ca;      --accent-hover: #3730a3;   --accent-ink: #ffffff;
  --accent-bg: #e0e7ff;   --accent-bg-ink: #3730a3;
  --success: #065f46;     --success-bg: #d1fae5;
  --danger: #b42318;      --danger-bg: #fef3f2;      --info-bg: #eef4ff;
  --focus: #4338ca;
  --shadow-card: 0 1px 2px rgb(0 0 0 / 0.06);
  --shadow-raised: 0 6px 20px rgb(0 0 0 / 0.1);
  --radius: 0.75rem;      --topbar-height: 3.5rem;
  --font: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) {
    --bg: #151517;        --surface: #1f1f22;
    --ink: #f2f0ec;       --muted: #b0aaa3;
    --line: #3a3936;      --line-strong: #7c776f;
    --accent: #a5b4fc;    --accent-hover: #c7d2fe;   --accent-ink: #0f0e2a;
    --accent-bg: #26254f; --accent-bg-ink: #c7d2fe;
    --success: #6ee7b7;   --success-bg: #0f2a22;
    --danger: #fda29b;    --danger-bg: #3a1512;      --info-bg: #172447;
    --focus: #a5b4fc;
    --shadow-card: none;  --shadow-raised: none;
  }
}
:root[data-theme='dark'] { /* the same values as the dark block above */ }
```

The dark values are written twice, because CSS has no way to share a block between a media query and an attribute selector. A test (section 4, step 1) fails if the two blocks differ.

### 3.2 Provider card

Built from the real `SearchResult`, `t()`, `formatRate` and `RevealMobile`. This replaces `ResultCard` in `SearchPage.tsx`.

```tsx
const MAX_PILLS = 4

/** How many of the searched skills the provider has, without regard to case; null when none are searched. */
export function skillMatch(item: SearchResult, searched: string[]) {
  if (searched.length === 0) return null
  const have = new Set(item.skills.map((skill) => skill.name.toLowerCase()))
  return { have: searched.filter((name) => have.has(name.toLowerCase())).length, of: searched.length }
}

function ProviderCard({ item, search, searchedSkills, matchAny, own }: {
  item: SearchResult
  search: string
  searchedSkills: string[]
  matchAny: boolean // the "all" filter makes every result a full match, so it is not shown
  own: boolean
}) {
  const name = item.full_name ?? t('search.noName')
  const match = matchAny ? skillMatch(item, searchedSkills) : null
  const extra = item.skills.length - MAX_PILLS
  return (
    <li className="card pcard">
      <h2 className="pcard-name">
        <span className="pcard-initials" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
        <Link className="pcard-link" to={`${PERSON_PROVIDERS}/${item.id}`} state={{ search }}>{name}</Link>
      </h2>
      <p className="pcard-rate">
        <strong>{formatRate(item.rate_per_hour, item.rate_currency)}</strong>{' '}
        {item.is_rate_negotiable && <Badge tone="good">{t('search.negotiableTag')}</Badge>}
      </p>
      <p className="pcard-trust">
        <ShieldIcon />
        {t('search.trustLine', { church: item.church.name, group: item.home_group.name })} {/* new key */}
      </p>
      {match && <p className="pcard-match">{t('search.skillMatch.of', match)}</p>} {/* new key: "{have} of {of} searched skills" */}
      <ul className="pills plain-list" aria-label={t('search.skillsLabel')}> {/* new key */}
        {item.skills.slice(0, MAX_PILLS).map((skill) => (
          <li key={skill.name} className="pill">{skill.level ? `${skill.name} · ${skill.level}` : skill.name}</li>
        ))}
        {extra > 0 && <li className="pill pill-more">{t('search.moreSkills', { count: extra })}</li>} {/* new key */}
      </ul>
      <p className="muted">{[item.nationality, ...item.languages].filter(Boolean).join(' · ')}</p>
      {!own && (
        <div className="pcard-foot">
          <RevealMobile freelancerId={item.id} freelancerName={name} source="search" searchedSkills={searchedSkills} />
        </div>
      )}
    </li>
  )
}
```

`ShieldIcon` is a 16px inline SVG with `aria-hidden`; the words carry the meaning. The rating line of today's card stays between the rate and the trust line.

```css
/* Mobile first: one column; wider screens add columns to the grid, not to the card. */
.result-grid { grid-template-columns: 1fr; }
@media (min-width: 640px) {
  .result-grid { grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); }
}

.pcard {
  position: relative; display: grid; gap: 0.75rem; padding: 1rem;
  box-shadow: var(--shadow-card);
  transition: box-shadow 120ms ease-out, border-color 120ms ease-out;
}
@media (min-width: 640px) { .pcard { padding: 1.25rem; } }
.pcard:hover, .pcard:focus-within { border-color: var(--line-strong); box-shadow: var(--shadow-raised); }

.pcard-name { display: flex; align-items: center; gap: 0.75rem; margin: 0; font-size: 1.125rem; }
.pcard-initials {
  display: grid; place-items: center; flex: none; width: 2.5rem; height: 2.5rem;
  border-radius: 999px; background: var(--accent-bg); color: var(--accent-bg-ink); font-weight: 650;
}
/* The link covers the whole card; Reveal stays above it. The ring is drawn on the card. */
.pcard-link { color: var(--ink); text-decoration: none; }
.pcard-link::after { content: ''; position: absolute; inset: 0; border-radius: var(--radius); }
.pcard-link:focus-visible { outline: none; }
.pcard-link:focus-visible::after { outline: 3px solid var(--focus); outline-offset: 2px; }
.pcard-foot { position: relative; z-index: 1; }

.pcard-rate { margin: 0; font-variant-numeric: tabular-nums; color: var(--muted); }
.pcard-rate strong { color: var(--ink); font-size: 1.125rem; }
.pcard-trust {
  display: flex; align-items: center; gap: 0.5rem; margin: 0; padding: 0.25rem 0.75rem;
  border-radius: 999px; font-size: 0.875rem; color: var(--success); background: var(--success-bg);
}
.pcard-match { margin: 0; font-size: 0.875rem; color: var(--muted); }

.pills { display: flex; flex-wrap: wrap; gap: 0.375rem; margin: 0; }
.pill { padding: 0.125rem 0.625rem; border-radius: 999px; font-size: 0.75rem; font-weight: 500;
        background: var(--accent-bg); color: var(--accent-bg-ink); }
.pill-more { background: transparent; color: var(--muted); border: 1px solid var(--line-strong); }

@media (prefers-reduced-motion: reduce) { .pcard { transition: none; } }
```

### 3.3 Navigation

```ts
// shell/nav.ts: the one place that decides what a status sees.
export type NavLinkItem = { to: string; label: string }
export type NavGroup = { id: string; label: string; links: NavLinkItem[] }

export function navFor(person: PersonMe): NavGroup[] {
  const searcher = atLeast(person, 'searcher')
  const provider = atLeast(person, 'provider')
  const leader = atLeast(person, 'verifier')
  const admin = atLeast(person, 'admin')
  const groups: NavGroup[] = []
  if (searcher) groups.push({ id: 'find', label: t('member.nav.label'), links: [/* search, ratings given */] })
  if (provider) groups.push({ id: 'services', label: t('nav.services'), links: [/* profile, skills, availability, ratings */] })
  if (leader) groups.push({ id: 'church', label: t('leader.nav.label'), links: [/* applicants … moves, flagged, revoked */] })
  if (admin) groups.push({ id: 'admin', label: t('nav.admin'), links: [/* groups, reports, handover */] })
  if (person.status === 'owner') groups.push({ id: 'owner', label: t('nav.owner'), links: [/* views, labels, churches */] })
  return groups
}
```

`atLeast` is the status order `searcher < provider < verifier < admin < owner`, written once (`PersonLayout` spells it out as arrays today). Its test is a table: every status against the links it must have and must not have, like the permission matrix on the server. That table is what stops a later change from showing My services to a SEARCHER. *New keys:* `nav.services`, `nav.admin`, `nav.owner`.

```tsx
function GroupMenu({ group, panel = false }: { group: NavGroup; panel?: boolean }) {
  // panel: inside the mobile Menu panel the group is a heading over an open list, with no button.
  const [open, setOpen] = useState(false)
  const id = useId()
  const box = useRef<HTMLDivElement>(null)
  return (
    <div
      className="navgroup" ref={box}
      onKeyDown={(e) => { if (e.key === 'Escape' && open) { setOpen(false); box.current?.querySelector('button')?.focus() } }}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false) }}
    >
      {panel ? (
        <h2 className="navgroup-title">{group.label}</h2>
      ) : (
        <button type="button" className="btn btn-quiet" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
          {group.label}
        </button>
      )}
      <ul id={id} className="navgroup-list plain-list" hidden={!panel && !open}>
        {group.links.map((link) => (
          <li key={link.to}><NavLink to={link.to} onClick={() => setOpen(false)}>{link.label}</NavLink></li>
        ))}
      </ul>
    </div>
  )
}
```

```css
/* Base (mobile): inside the Menu panel the groups are stacked, always open, no floating list. */
.navgroup-list { margin: 0; padding: 0; }
.navgroup-list a { display: flex; align-items: center; min-height: 2.75rem; padding: 0.5rem 0.75rem;
                   border-radius: 0.5rem; color: var(--ink); text-decoration: none; }
.navgroup-list a:hover { background: var(--bg); }
.navgroup-list a[aria-current='page'] { background: var(--accent-bg); color: var(--accent-bg-ink); font-weight: 650; }

/* From 640px: each group is a button with a floating list. */
@media (min-width: 640px) {
  .navgroup { position: relative; }
  .navgroup-list { position: absolute; inset-block-start: 100%; inset-inline-start: 0; z-index: 30;
                   min-width: 14rem; padding: 0.5rem; background: var(--surface);
                   border: 1px solid var(--line); border-radius: var(--radius);
                   box-shadow: var(--shadow-raised); }
}
```

On mobile the Menu panel renders each group with `panel` set, so the lists are open under headings and no extra tap is needed. From 640px the bar renders them without it. The component and this sentence must stay in agreement. `NavLink` sets `aria-current="page"` itself.

## 4. Build order

Each step is its own change, after review. (The first release of the design was built as a single pull request, at the owner's request.) Each one updates [06-frontend.md](specification/06-frontend.md) where behaviour changes, and passes the existing checks (frontend tests, lint, typecheck and the Playwright layout run at five viewports).

1. **Tokens and theme.** Replace the token block, add the theme script and the System / Light / Dark choice on the account page, and the font if the owner agrees. No markup change except the script. Check every screen in both themes. Add a unit test that reads the token blocks of `global.css` and fails if a pair in the contrast table is below its threshold, or if the dark `data-theme` block differs from the media block. Add an axe run to the Playwright scenarios in both themes.
2. **Navigation.** `navFor` with its status table, group menus, the Menu panel on mobile, the Account menu, the name field. Update `responsive.spec.ts` for the new bar, including a leader on a 320px phone with no sideways scroll.
3. **Provider card and results grid.** `ProviderCard` and `skillMatch` (tests: none searched, any, all, case, a skill missing, own card without Reveal), the grid and the skeletons. The Reveal tests do not change.
4. **Live filters on desktop.** Debounced apply from 1024px, dimmed old results, the live region, empty states. Test that the URL is the one source of state and that a slow older response never overwrites a newer one.
5. **Member home.** Tiles ordered by status, "Find {freelancers}" first.
6. **Name suggestions and `/`.** Only if the owner wants them (section 5).
7. **Provider panel.** Optional. Section 2.5 holds the requirements.

The Android app is not part of these steps. It has its own theme in `mobile/lib/`. If the owner wants the same indigo there, that is a separate change with its own contrast checks. [parity.md](android/parity.md) is about screens and behaviour and does not change.

## 5. Open points for the owner

Each has a default that this document already assumes.

1. **The leader's name on the card.** The search response has the home group's id and name only. "Led by A. Mensah" needs `leader_name` added to the search result, a small change to the API and specification that exposes no new data (the home group already has a leader, and the sign-up screens show it). Default: not shown until then.
2. **Skill match.** "3 of 4 searched skills", worked out in the browser, only with *any*. A weighted score or a "best match" sort needs the API first. Default: the simple count, no sort.
3. **Bottom tab bar on mobile.** Default: **no**. One Menu button with grouped links (section 2.2).
4. **Inter, self-hosted.** About 100 KB. Default: yes, with `system-ui` as the fallback. Say no, and step 1 uses `system-ui` only.
5. **Provider slide-over.** Default: not in the first release. The provider's page stays a page (section 2.5).
6. **Name suggestions and the `/` key.** Default: later (step 6).
7. **Indigo replaces teal.** The accent today is teal (`#0A6C6C`). Default: indigo, as proposed. Say so now if teal means something to the church or its logo.
8. **Tailwind.** Not adopted. The tokens are plain CSS variables and map to a Tailwind theme if it is ever wanted. That would be its own decision.
