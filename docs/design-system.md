# Design system and UI specification

Status: proposal, 2026-11-15. Not yet built. It changes no data, roles or permissions, so [verification.md](verification.md) is unchanged.

Direction: **Dark Graphite & Warm Stone**, with an **Electric Indigo** call to action and **Emerald** for trust. Desktop first, then tablet and mobile. Built for fast scanning and few clicks. The target is WCAG 2.2 AA.

## 0. How the brief maps to Skills

Skills is a closed church network with no jobs, budgets, payments or clients. The design keeps the interaction patterns and fits them to the model in [verification.md](verification.md):

| Brief | In Skills | Why |
|---|---|---|
| Job feed, job card | **Provider feed, provider card** | The things searched are providers (FR-S-06) |
| Budget badge | **Rate badge** (rate, currency, negotiable) | FR-P-02 |
| Payment verified / verified client | **Vouched** tag: church, home group and leader | Trust comes from the home group, not payment. Every listed provider is already admitted, so the tag shows *who stands behind them*, not a yes or no |
| Find Work / Hire Talent toggle | **Search** (everyone admitted) and **My services** (PROVIDER and above) | A higher status includes the lower, so this is a view switch, not a role switch. A SEARCHER never sees My services |
| Match percentage | **Skill match**: searched skills the provider has, out of those searched | Derived from the existing skill filter. Shown only when skills are filtered |
| Rate range | Maximum rate, currency, negotiable only (FR-S-02) | |
| Timezone overlap | **Available on** a date range (FR-S-03) | The app has no timezones |
| Engagement type | **Timing** (FR-S-01) | |
| Skill tags | Skill any/all, level, language, nativity (FR-S-01) | |
| Apply from the slide-over | **Reveal mobile** and **Rate** (FR-M-05, FR-M-06) | The contact action is the conversion |

Do not add a field the API does not have. If the skill match needs data the search response lacks, change the API and the specification first.

## 1. Visual system

### 1.1 Colour tokens

Every pair below was computed against the WCAG 2.2 contrast formula. Thresholds: text 4.5:1, large text 3:1, UI boundaries and focus rings 3:1.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` canvas | `#F5F3EF` | `#151517` | Page background |
| `--surface` card | `#FFFFFF` | `#1F1F22` | Cards, drawer, header |
| `--ink` primary text | `#1C1B19` | `#F2F0EC` | Body, headings |
| `--ink-2` secondary text | `#57534E` | `#B0AAA3` | Labels, metadata |
| `--ink-3` muted text | `#6B665F` | `#9A948C` | Hints, timestamps |
| `--line` muted border | `#D6D3CD` | `#3A3936` | Card and divider lines (decorative only) |
| `--line-strong` | `#8C877F` | `#7C776F` | Input, checkbox and toggle edges |
| `--cta` indigo | `#4338CA` | `#A5B4FC` | Primary button fill, links, focus ring |
| `--cta-hover` | `#3730A3` | `#C7D2FE` | Hover and pressed |
| `--cta-ink` | `#FFFFFF` | `#0F0E2A` | Text on the CTA |
| `--cta-bg` | `#E0E7FF` | `#26254F` | Selected chips and the active toggle |
| `--cta-bg-ink` | `#3730A3` | `#C7D2FE` | Text on `--cta-bg` |
| `--ok` emerald | `#047857` | `#34D399` | Vouched icon and text on a surface |
| `--ok-bg` | `#D1FAE5` | `#0F2A22` | Vouched tag background |
| `--ok-ink` | `#065F46` | `#6EE7B7` | Text on `--ok-bg` |
| `--danger` | `#B42318` | `#FDA29B` | Errors, revoke |

Computed contrast ratios:

| Pair | Light | Dark |
|---|---|---|
| `--ink` on canvas | 15.53 | 16.02 |
| `--ink` on surface | 17.21 | 14.44 |
| `--ink-2` on canvas / surface | 6.88 / 7.63 | 7.92 / 7.14 |
| `--ink-3` on canvas / surface | 5.13 / 5.69 | 5.47 on surface |
| `--line-strong` on canvas / surface | 3.22 / 3.57 | 4.10 / 3.70 |
| `--cta-ink` on `--cta` | 7.90 | 9.43 |
| `--cta-ink` on `--cta-hover` | 9.93 | 12.61 |
| `--cta` on surface (links, focus ring) | 7.90 | 8.25 |
| `--cta-bg-ink` on `--cta-bg` | 8.06 | 9.64 |
| `--ok` on surface | 5.48 | 8.55 |
| `--ok-ink` on `--ok-bg` | 6.78 | 10.02 |
| `--danger` on surface | 6.57 | 8.47 |

Rules:

- **Colour is never the only signal.** The Vouched tag carries a shield icon and the words "Vouched". A selected filter carries a tick. An error carries an icon and text.
- **Warm stone for the canvas, a clean surface for cards.** The contrast between them is deliberately small, so a card edge uses `--line` as a hairline plus a soft shadow in light mode. Dark mode uses the surface step alone. A card's edge is decorative, because the text inside it is the content.
- **Form controls use `--line-strong`** (WCAG 1.4.11).
- Dark mode follows `prefers-color-scheme`, with a manual override saved per person in the browser. It never flashes on load: set `data-theme` from an inline script in `index.html`.

### 1.2 Typography

| Role | Face | Notes |
|---|---|---|
| UI and body | **Inter** (variable), fallback `system-ui` | Tall x-height and clear digits for dense data. Use `font-feature-settings: 'tnum', 'cv11'` so rates align |
| Headings | Inter at 650 weight, tight tracking | One family keeps the payload small |
| Mono (ids, codes) | `ui-monospace` | |

Self-host the font files. The privacy page makes a promise about third parties, and a font CDN would break it.

| Step | Size / line height | Weight | Use |
|---|---|---|---|
| Display | 30 / 36 | 650 | Landing only |
| H1 | 24 / 32 | 650 | Page title |
| H2 | 20 / 28 | 600 | Section, drawer title |
| H3 | 16 / 24 | 600 | Card title |
| Body | 14 / 20 | 400 | Default in dense lists |
| Body large | 16 / 24 | 400 | Forms and mobile body |
| Caption | 12 / 16 | 500 | Meta and pills, never below 12px |

Mobile body is 16px. Anything smaller makes iOS zoom into a focused input.

### 1.3 Space, shape, motion

- 4px base scale: 4, 8, 12, 16, 24, 32, 48. Card padding 16 on mobile, 20 from tablet up.
- Radius: 8 controls, 12 cards, 999 pills.
- Elevation: card rest `0 1px 2px rgb(0 0 0 / .06)`, hover `0 6px 20px rgb(0 0 0 / .10)`. Dark mode drops shadows and lifts the surface by 4% instead.
- Motion: 120ms for hover and 220ms for the drawer, with an ease-out curve. Under `prefers-reduced-motion: reduce`, drop all transforms and use plain fades or no animation.
- Targets: at least 44 × 44px on touch screens (WCAG 2.5.8 asks for 24 × 24, and 44 is the platform norm). Visible focus ring: 2px `--cta` with a 2px offset, on every interactive element.

## 2. Layout and interaction architecture

### 2.1 Breakpoints

| Name | Width | Layout |
|---|---|---|
| Desktop (first) | ≥ 1024px | Filter rail 280px, feed fills the rest. The detail drawer is a 480px slide-over |
| Tablet | 640–1023px | Filters collapse behind one **Filters** button into a left drawer. The feed has 2 columns. The detail drawer is 60% wide |
| Mobile | < 640px | One column. A bottom tab bar replaces the header links. Filters open as a full-height sheet, and the detail opens as a full-screen sheet |

### 2.2 Top navigation (sticky)

```
Desktop
[Skills]  [ Search | My services ]   [ 🔍 Search skills, people …  ⌘K ]   [🔔 3]  [Avatar ▾]

Mobile
[Skills]                                  [🔍] [🔔 3] [Avatar]
────────────────────────────────────────────────────────────
 … page …
────────────────────────────────────────────────────────────
[ Search ]   [ My services* ]   [ Alerts ]   [ Me ]     (* PROVIDER and above)
```

- **Sticky**, 56px, `--surface` with a bottom hairline. It sits above content with `z-index` 40, and the skip link remains the first tab stop.
- **Mode toggle** is a two-option segmented control (`role="tablist"` is wrong here because it navigates, so use `<nav>` with two links and `aria-current="page"`). It changes the route, so the Back button works and the view can be bookmarked. The active option uses `--cta-bg` and bold text, so it reads in greyscale. **A SEARCHER sees no toggle at all, only Search.** Leaders keep their own screens (Applicants, Members, Groups) in the avatar menu, not the toggle.
- **Global search** is a single field with the skill any/all search behind it. `/` or `⌘K` focuses it. Typing opens a suggestion list (skills first, then people) as a `role="combobox"` with `aria-activedescendant`. Enter goes to the feed with the query as a URL parameter. On mobile the field is an icon that expands to a full-width bar.
- **Notification hub** is a bell with an unread count and a text label for screen readers ("3 unread"). The panel lists the latest items. Each item links to its page, and "Mark all read" sits at the top. The count uses the existing poll (`NOTIFICATIONS_POLL_MS`).
- **Avatar menu**: Profile, Availability, My vouches, Account, Downloads, theme, Sign out, plus the leader, admin and owner screens that the person's status allows.
- A REVOKED or PENDING person sees none of this, only the page they are allowed to see.

### 2.3 Search and filter drawer

Filters apply **as you change them**, with no Apply button and no reload. The state lives in the URL (as `searchParams.ts` does now), so a refresh, a share and Back all work. Requests are debounced by 250ms and cancel the previous one, and the previous results stay visible, dimmed, until the new ones arrive. A polite live region announces "48 providers".

| Filter | Control | Requirement |
|---|---|---|
| Skills | Tag input with suggestions, plus **Any / All** switch, then level | FR-S-01 |
| Maximum rate | Slider with a number field, then currency, then **Negotiable only** checkbox | FR-S-02 |
| Available on | Date range picker | FR-S-03 |
| Church / home group | Two linked selects | FR-S-04 |
| Minimum rating | Stepper 1–10 | FR-S-04 |
| Language, timing, nativity | Checkbox groups | FR-S-01 |
| Sort | Select: Best match, Rating, Rate, Newest | FR-S-05 |

- A strip of **removable chips** above the feed shows every active filter, each with a remove button and "Clear all". It reuses `activeFilters.ts`.
- The count on the mobile **Filters** button shows the number active.
- An empty result says which filter to relax, with a one-click action (for example "Remove 'Negotiable only'").
- Every control has a visible label. The rate slider has a number field twin, because a slider alone is hard to use with a keyboard or a screen reader.

### 2.4 Provider feed (bento grid)

- CSS grid, `repeat(auto-fill, minmax(300px, 1fr))`, 16px gap. Desktop shows 2–3 columns beside the filter rail.
- **Bento rule:** all cards have equal width. A card spans two columns only when it is the *top match* (rank 1 under Best match) on desktop, and carries a short bio line. Nothing else changes size, so scanning stays predictable.
- Pagination is a "Load more" button with a count ("Showing 24 of 312"). Infinite scroll is avoided, because it traps keyboard users and loses their place.
- The loading state is skeleton cards of the same size, with no layout shift.

**Card hierarchy** (top to bottom, the order of reading):

1. **Name**, picture, and the **Skill match** ring (for example "3/4 skills") when skills are filtered
2. **Rate** badge (the main scan target, aligned top right), plus "Negotiable"
3. Primary skill, with the level
4. **Vouched** tag: "Grace Church · Home group Oak · led by A. Mensah"
5. **Skill pills**, at most 4, then "+3 more"
6. Footer: rating (★ 8.6 · 12), availability line, and the **Reveal mobile** button

The whole card opens the drawer. The Reveal button stops propagation and works on its own.

### 2.5 Detail slide-over

- Opens from the card without leaving the feed. The URL gains `?provider=<id>`, so Back closes it and a link opens it.
- Desktop: a 480px panel from the right over a scrim at 40% opacity. Tablet: 60% wide. Mobile: full-screen sheet from the bottom.
- It is a `role="dialog"` with `aria-modal`, a labelled title and a focus trap. Esc and the scrim close it, and focus returns to the card.
- Content: header (name, rate, Vouched tag), sticky action bar (**Reveal mobile**, **Rate**), skills and levels, languages, availability, church and home group with the leader's name, ratings list.
- **Previous / Next** buttons (and `J` / `K`) move through the feed while the drawer stays open, so a person can triage many providers quickly.
- The action bar stays pinned at the bottom of the panel, so the primary action is never below the fold.
- Reveal follows FR-M-05 to FR-M-07: the number is greyed out until the server returns it, and a `429` shows the wait time.

### 2.6 Zero-friction rules

1. The first screen after sign-in for a SEARCHER or above is the feed, with the last filters restored.
2. No full-page reloads for filtering, opening a provider or changing sort.
3. Every filter, sort and drawer state is in the URL.
4. Keyboard: `/` search, `J`/`K` next and previous card, `Enter` open, `Esc` close, `R` reveal (in the drawer). List the shortcuts in a help dialog (`?`), and never trigger them while typing in a field.
5. Destructive or irreversible actions (revoke, leave) keep the existing `Confirm` dialog.

## 3. Components

The frontend uses plain CSS with variables (see `frontend/src/styles/global.css`) and has no Tailwind, so the components below use **React + CSS variables**. Tailwind can be added later by mapping the same tokens in its theme. That is a separate decision.

### 3.1 Tokens

```css
:root {
  --bg: #f5f3ef;        --surface: #ffffff;
  --ink: #1c1b19;       --ink-2: #57534e;      --ink-3: #6b665f;
  --line: #d6d3cd;      --line-strong: #8c877f;
  --cta: #4338ca;       --cta-hover: #3730a3;  --cta-ink: #ffffff;
  --cta-bg: #e0e7ff;    --cta-bg-ink: #3730a3;
  --ok: #047857;        --ok-bg: #d1fae5;      --ok-ink: #065f46;
  --danger: #b42318;
  --radius: 0.75rem;
  --font: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) {
    --bg: #151517;      --surface: #1f1f22;
    --ink: #f2f0ec;     --ink-2: #b0aaa3;      --ink-3: #9a948c;
    --line: #3a3936;    --line-strong: #7c776f;
    --cta: #a5b4fc;     --cta-hover: #c7d2fe;  --cta-ink: #0f0e2a;
    --cta-bg: #26254f;  --cta-bg-ink: #c7d2fe;
    --ok: #34d399;      --ok-bg: #0f2a22;      --ok-ink: #6ee7b7;
    --danger: #fda29b;
  }
}
:root[data-theme='dark'] { /* the same values as the dark block above */ }
```

### 3.2 Provider card

```tsx
import type { ProviderSummary } from '../../api/types'

type Props = {
  provider: ProviderSummary
  matched?: { have: number; of: number } // only when skills are filtered
  featured?: boolean                      // the top match on desktop
  onOpen: (id: string) => void
  onReveal: (id: string) => void
}

export function ProviderCard({ provider: p, matched, featured, onOpen, onReveal }: Props) {
  const maxPills = 4
  const extra = p.skills.length - maxPills
  return (
    <article className={`pcard${featured ? ' pcard--featured' : ''}`}>
      <button
        type="button"
        className="pcard-open"
        onClick={() => onOpen(p.id)}
        aria-label={`Open ${p.name}`}
      />
      <header className="pcard-head">
        <img className="pcard-pic" src={p.picture} alt="" width={44} height={44} />
        <div className="pcard-who">
          <h3 className="pcard-name">{p.name}</h3>
          <p className="pcard-sub">{p.skills[0]?.name} · {p.skills[0]?.level}</p>
        </div>
        <p className="pcard-rate" aria-label={`Rate ${p.rate} ${p.currency} per hour`}>
          <strong>{p.rate}</strong> {p.currency}/h
          {p.rate_negotiable && <span className="pcard-neg">Negotiable</span>}
        </p>
      </header>

      <p className="tag tag-ok">
        <ShieldIcon aria-hidden />
        <span>Vouched</span>
        <span className="tag-sub">{p.church} · {p.home_group} · led by {p.leader_name}</span>
      </p>

      {matched && (
        <p className="pcard-match">
          <span className="meter" role="img" aria-label={`${matched.have} of ${matched.of} skills match`}>
            <span style={{ width: `${(matched.have / matched.of) * 100}%` }} />
          </span>
          {matched.have}/{matched.of} skills
        </p>
      )}

      <ul className="pills" aria-label="Skills">
        {p.skills.slice(0, maxPills).map((s) => (
          <li key={s.id} className="pill">{s.name}</li>
        ))}
        {extra > 0 && <li className="pill pill-more">+{extra} more</li>}
      </ul>

      <footer className="pcard-foot">
        <span>★ {p.average_rating?.toFixed(1) ?? '–'} <span className="muted">({p.rating_count})</span></span>
        <button type="button" className="btn btn-primary" onClick={() => onReveal(p.id)}>
          Reveal mobile
        </button>
      </footer>
    </article>
  )
}
```

The field names above are illustrative. Bind them to the real `FreelancerPublic` type in `frontend/src/api/types.ts` when building.

```css
.pcard {
  position: relative; display: grid; gap: 12px; padding: 20px;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.06);
  transition: transform 120ms ease-out, box-shadow 120ms ease-out, border-color 120ms;
}
.pcard:hover, .pcard:focus-within {
  transform: translateY(-2px); border-color: var(--line-strong);
  box-shadow: 0 6px 20px rgb(0 0 0 / 0.1);
}
.pcard--featured { grid-column: span 2; }
@media (max-width: 1023px) { .pcard--featured { grid-column: auto; } }
/* The whole card is one click target, with the real button covering it. */
.pcard-open { position: absolute; inset: 0; border: 0; background: none; border-radius: inherit; cursor: pointer; }
.pcard-open:focus-visible { outline: 2px solid var(--cta); outline-offset: 2px; }
.pcard-foot .btn, .pcard a { position: relative; z-index: 1; } /* above the cover button */

.pcard-head { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; }
.pcard-pic  { border-radius: 999px; object-fit: cover; }
.pcard-name { font-size: 16px; line-height: 24px; font-weight: 600; margin: 0; }
.pcard-sub  { color: var(--ink-2); font-size: 14px; margin: 0; }
.pcard-rate { text-align: right; margin: 0; font-variant-numeric: tabular-nums; color: var(--ink-2); }
.pcard-rate strong { color: var(--ink); font-size: 18px; }
.pcard-neg  { display: block; font-size: 12px; color: var(--ink-3); }

.tag { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; margin: 0;
       padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; }
.tag-ok { background: var(--ok-bg); color: var(--ok-ink); }
.tag-ok svg { color: var(--ok); width: 14px; height: 14px; }
.tag-sub { font-weight: 400; }

.meter { display: inline-block; width: 64px; height: 6px; margin-right: 8px; border-radius: 99px;
         background: var(--line); vertical-align: middle; overflow: hidden; }
.meter > span { display: block; height: 100%; background: var(--cta); }
.pcard-match { margin: 0; color: var(--ink-2); font-size: 13px; }

.pills { display: flex; flex-wrap: wrap; gap: 6px; padding: 0; margin: 0; list-style: none; }
.pill { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 500;
        background: var(--cta-bg); color: var(--cta-bg-ink); }
.pill-more { background: transparent; color: var(--ink-2); border: 1px solid var(--line-strong); }

.pcard-foot { display: flex; justify-content: space-between; align-items: center; }
.btn-primary { min-height: 44px; padding: 0 16px; border: 0; border-radius: 8px; font: inherit; font-weight: 600;
               background: var(--cta); color: var(--cta-ink); cursor: pointer; }
.btn-primary:hover { background: var(--cta-hover); }
.btn-primary:focus-visible { outline: 2px solid var(--cta); outline-offset: 2px; }

@media (prefers-reduced-motion: reduce) { .pcard { transition: none; } .pcard:hover { transform: none; } }
```

Two accessibility notes: the meter is not the only signal (the "3/4 skills" text sits beside it), and the card uses a cover button instead of a link inside a link, so a screen reader reads one clear control, "Open Name".

### 3.3 Top navigation with the mode toggle

```tsx
import { NavLink } from 'react-router-dom'

type Props = { canProvide: boolean; unread: number }

export function TopNav({ canProvide, unread }: Props) {
  return (
    <header className="topnav">
      <a className="skip-link" href="#main">Skip to content</a>
      <NavLink to="/" className="brand">Skills</NavLink>

      {canProvide && (
        <nav className="mode" aria-label="View">
          <NavLink to="/search" className="mode-opt">Search</NavLink>
          <NavLink to="/my-services" className="mode-opt">My services</NavLink>
        </nav>
      )}

      <form className="gsearch" role="search" action="/search">
        <label htmlFor="gs" className="sr-only">Search skills and people</label>
        <input id="gs" name="q" type="search" placeholder="Search skills, people…" autoComplete="off" />
        <kbd aria-hidden>/</kbd>
      </form>

      <NavLink to="/notifications" className="bell" aria-label={`Notifications, ${unread} unread`}>
        <BellIcon aria-hidden />
        {unread > 0 && <span className="bell-n" aria-hidden>{unread}</span>}
      </NavLink>
      <AvatarMenu />
    </header>
  )
}
```

```css
.topnav { position: sticky; top: 0; z-index: 40; display: flex; align-items: center; gap: 16px;
          height: 56px; padding: 0 24px; background: var(--surface); border-bottom: 1px solid var(--line); }
.brand { font-weight: 650; font-size: 18px; color: var(--ink); text-decoration: none; }

.mode { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--bg);
        border: 1px solid var(--line-strong); }
.mode-opt { padding: 6px 16px; border-radius: 999px; font-size: 14px; font-weight: 500;
            color: var(--ink-2); text-decoration: none; min-height: 32px; }
.mode-opt:hover { color: var(--ink); }
.mode-opt[aria-current='page'] { background: var(--cta-bg); color: var(--cta-bg-ink); font-weight: 650; }
.mode-opt:focus-visible { outline: 2px solid var(--cta); outline-offset: 2px; }

.gsearch { position: relative; flex: 1; max-width: 520px; margin: 0 auto; }
.gsearch input { width: 100%; height: 40px; padding: 0 40px 0 14px; font: inherit; color: var(--ink);
                 background: var(--bg); border: 1px solid var(--line-strong); border-radius: 999px; }
.gsearch input:focus { outline: 2px solid var(--cta); outline-offset: 1px; }
.gsearch kbd { position: absolute; right: 14px; top: 10px; font-size: 12px; color: var(--ink-3);
               border: 1px solid var(--line-strong); border-radius: 4px; padding: 0 5px; }

.bell { position: relative; display: grid; place-items: center; width: 44px; height: 44px; color: var(--ink); }
.bell-n { position: absolute; top: 4px; right: 2px; min-width: 18px; padding: 0 5px; border-radius: 99px;
          font-size: 11px; font-weight: 700; text-align: center; background: var(--cta); color: var(--cta-ink); }

@media (max-width: 1023px) { .topnav { padding: 0 16px; gap: 8px; } .gsearch kbd { display: none; } }
@media (max-width: 639px) {
  .mode { display: none; }            /* the bottom tab bar carries it on mobile */
  .gsearch { margin: 0; }
}
```

The `canProvide` flag is `provider`, `verifier`, `admin` or `owner`, exactly as `PersonLayout.tsx` already works out. Keep that one rule in one place.

## 4. Build order

1. Tokens and dark mode in `global.css` (no markup change). Check every existing screen for contrast.
2. Top navigation and the mobile tab bar.
3. Provider card and the feed grid.
4. Live filters and the chip strip.
5. Detail slide-over (route driven).
6. Keyboard shortcuts and the help dialog.

Each step is its own change, with tests for focus handling, the URL state and the status-based visibility of "My services". Add an automated contrast check over the token table above, and an axe run in the Playwright end-to-end tests.

## 5. Open points for the product owner

- **Skill match:** is "x of y searched skills" enough, or is a weighted score wanted? A weighted score needs the API changed first.
- **Mobile bottom tabs vs. the existing top bar:** the plan above moves primary links to the bottom on mobile. Confirm that before step 2.
- **Inter:** the file adds about 100 KB self-hosted. Keep `system-ui` instead if that is too heavy.
- **Tailwind:** only if wanted, as a separate decision, mapping the tokens above to its theme.
