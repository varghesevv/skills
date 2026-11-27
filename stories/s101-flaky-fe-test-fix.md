### Background

The web test "searches by name and shows the name as a removable filter" (`frontend/src/pages/person/search/search.test.tsx`) fails now and then on CI with:

> Unable to find an element with the text: 1 freelancer(s) found

It failed in four CI runs, every time taking over 5.4 seconds:

| Run | Branch | Date |
|---|---|---|
| 43744108642 | `ci/mobile-release` | 2026-11-15 |
| 43746523684 | `main` | 2026-11-15 |
| 43815210298 | `chore/cleanups` | 2026-11-16 |
| 46002156844 | `main`, after #229 | 2026-11-27 |

It passes locally, and the same code passed CI again straight afterwards. S099 (#229) did not cause it: the failures began more than ten days earlier.

**The cause is a timing bug in the search page, not in the test.** `frontend/src/pages/person/search/SearchPage.tsx` keeps the text of the "Search by name" box in state, and copies the name from the address into it with an effect:

```tsx
const [nameText, setNameText] = useState(applied.name)
useEffect(() => {
  setNameText(applied.name)
}, [applied.name])
```

1. React runs an effect shortly after the page appears, not at the same moment, and this effect also runs once on the first render.
2. If the first keystroke comes in that gap, the effect then sets the box back to `''`, and the keystroke is lost.
3. In the failing CI run, the page's markup shows the box holding `value="nita"` instead of `anita`, and "Filters (1)". The page searched for `name=nita`.
4. The test's fake API does not expect that request, so it answers `404`. The page then shows "That item no longer exists. Reload the page." instead of the results.

On a fast machine the effect almost always runs before the test types, so the test passes. On a busy CI machine it sometimes does not.

For a person the gap is a few milliseconds right after the page opens, so they would only lose a letter by typing at that exact instant. It is still a real flaw, and the test was right to catch it.

### How it was confirmed (2026-11-27, on `main`)

- **Reproduced on demand.** A temporary test typed into the box the instant it appeared (found with a `MutationObserver`, before React ran its effects). It failed three times out of three with `value="nita"`. The box was the same element throughout, so the page was not rebuilt.
- **The fix was tried.** With the change below, the same test passed 36 times out of 36, and all 68 tests in `src/pages/person/search/` passed, including clearing the name from its filter chip.
- **The trial was undone.** The original code was put back and the temporary test deleted; nothing was committed.

### Feature Criteria

1. In `SearchPage.tsx`, replace the effect with React's recommended way of resetting state when a value changes, which is to adjust it during render. This leaves no gap after the first render:

   ```tsx
   const [nameText, setNameText] = useState(applied.name)
   const [shownName, setShownName] = useState(applied.name)
   if (shownName !== applied.name) {
     setShownName(applied.name)
     setNameText(applied.name)
   }
   ```

2. The box still follows the address, as today:
   - The name from a link (`/member/search?name=…`) or from the top bar's search fills the box.
   - Removing the name filter's chip, or clearing all filters, empties the box.
   - Back and forward in the browser update the box.
3. Check the other pages for the same pattern: state copied from a prop or from the address with a `useEffect` that also runs on the first render, in a field a person types into. Any found are fixed the same way, or listed in the PR if they cannot lose input.
4. Nothing else a person sees changes.

### Repositories affected:

Frontend: Yes

Backend: No

### Scope

The search page, and any page found by criterion 3. Do not perform any git push commands.

### Test Criteria

- **A regression test** in `search.test.tsx` types into "Search by name" the instant the box appears, before React's effects run, and checks the box holds the whole name. Without the fix it fails; with the fix it passes.
- The existing test at `search.test.tsx:84` is unchanged and passes.
- `npm run typecheck`, `npm run lint`, `npm test` and the Playwright tests pass.

### Definition of Done

The test suite passes, the regression test fails on the old code and passes on the new, and the search tests pass on CI without a rerun.

Note: story number S101 is also used by `s101-generated-api-types.md` on the `stories/frontend-quality` branch. One of the two should be renumbered before both reach `main`.
