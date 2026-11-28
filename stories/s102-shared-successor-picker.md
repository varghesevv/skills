### Background

Choosing a successor (a new home group leader or a new church ADMIN) is built five times in the web app, each with its own copy of the same steps: load the members of the church or group (`fetchMembers`), page through them, leave out the person being replaced, retry a failed load, say when the list is cut off ("Only the first N of M members are shown"), and turn `successor_not_member` into words. The copies are in:

- `frontend/src/pages/person/owner/Churches.tsx` (replace a church's ADMIN, and who leads their group)
- `frontend/src/pages/person/leader/Groups.tsx` (change the leader of a group)
- `frontend/src/pages/person/leader/RevokeAdmin.tsx` (revoke an ADMIN, with a new ADMIN and leader)
- `frontend/src/pages/person/leader/StatusControls.tsx` (revoke a VERIFIER with a successor)
- `frontend/src/pages/person/owner/Handover.tsx` (the OWNER's handover successors)

The verification model on branch `s100-initial-config` changes who may be chosen: a successor must be a **member** (SEARCHER or above, never a PENDING applicant), and may be a member of **another group of the same church** who moves in. With five copies, that rule would have to be changed five times.

### Feature Criteria

1. One shared component (for example `shared/SuccessorPicker.tsx`) and, if useful, one hook, used by all five screens. It takes: the scope (a home group or a church), who to leave out, the label, and what to do with the choice.
2. It keeps every behaviour the five copies have today: the same labels, paging and "only the first N of M" note, retry on a failed load, the same error wording, focus handling and accessibility.
3. Who may be chosen is decided in one place in the component, so the coming rule "members only (SEARCHER or above)" is a single change. This story does **not** change that rule; it only makes it one change.
4. The five screens lose their own copies; nothing else on those screens changes.

### Repositories affected:

Frontend: Yes

Backend: No

### Scope

Refactoring only: no change visible to users and no API change.

### Test Criteria

- The existing tests of the five screens pass unchanged (they test what people see, so they prove nothing changed).
- New tests for the shared component on its own: paging, the cut-off note, retry, leaving out the person being replaced, and the error wording.

### Definition of Done

The test suite passes, the five copies are gone, and the line count of the five screens goes down accordingly.
