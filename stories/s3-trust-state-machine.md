# S3: Trust state machine

## Story

As a **developer**, I want every change to a person's trust state to go through one module that checks it against the verification model, so that no feature can admit, appoint, revoke or move someone in a way the model does not allow, and every change is recorded in the chain of trust. The module must be loosely coupled, so the rules, the profiles and the features can each change without touching the others.

## Background

[ADR-0016](../docs/adr/0016-church-trust-hierarchy-verification-model.md) adopts [docs/verification.md](../docs/verification.md) as the trust and verification model. One of its consequences is "a single permissions module that mirrors `canSetStatus` and `canAdmit`". This story builds that module first, before the data model and the API exist, so later stories build on it instead of each writing its own checks.

The model is mostly a state machine over a person's status (REVOKED, PENDING, SEARCHER, PROVIDER, VERIFIER, ADMIN, OWNER), but not a simple one:

- **It depends on who is acting.** Whether a change is allowed depends on the actor's status, their scope (same group or same church), and who set the target's current status.
- **Some operations change several people at once.** A succession demotes one person and appoints another in the same step. Closing a church closes all its groups and accounts.
- **Some rules cover whole groups or churches,** such as one ADMIN per church and one leader per group, not just one person.

So the module works at the level of **operations**, not single status changes: an operation is checked against the current state and, if allowed, returns the full set of changes it makes.

## What goes through the module

Trust state only:

- `status`, `requestedStatus` and `flaggedForRecheck`
- membership: `churchId`, `homeGroupId`, `lastHomeGroupId`
- leadership: `HomeGroup.leaderId` and `Church.adminId`
- vouches, and withdrawing them
- closing accounts, home groups and churches (`closedAt`)
- `StatusChange` history

Ordinary profile details, such as name, picture, rate, skills and availability, do **not** go through it.

## Independence

The app is split into three models that are as independent as possible:

| Model | Holds | Examples |
|---|---|---|
| **Rules** (this module) | Who someone is in the trust hierarchy | Status, church, home group, leadership, vouches, history |
| **Profile** | What someone tells others about themselves | Name, picture, contact details, rate, skills, availability |
| **Features** | What people do in the app | Search, phone reveal, ratings, reports |

How they stay independent:

- **Linked by person id only.** The rules module's `Person` holds the id and the trust fields, nothing else. Profile tables refer to the person id; trust tables never refer to profile tables.
- **The rules module depends on nothing else.** It imports nothing from the rest of the app: no models, schemas, API routes, terminology or settings.
- **Everything else depends on a small public interface.** Other code calls the operations, `allowed_actions`, and capability questions such as `can_search(person)`, `can_be_listed(person)` and `can_vouch(person)`. Feature code never compares status values itself, so changing which status may do what is a change to the rules module only.
- **Storage goes through a port.** The module defines what it needs from storage: load the state an operation needs, and apply a change set in one transaction. The app supplies a database adapter; tests use an in-memory one.
- **Wording stays outside.** The module uses stored names only. Display words such as "Home group" or "Provider" come from the terminology profiles, as they do today.

Contact details (email and phone) belong to the profile model. Keeping them unique among open accounts, as the verification model requires, is a profile rule that asks the rules module whether an account is open.

## Design

A backend package, for example `backend/app/trust/`, with no database or web code in its decision logic:

1. **Plain types** that mirror the [Data model summary](../docs/verification.md#data-model-summary): `Status`, `Person`, `Church`, `HomeGroup`, `Vouch`, `StatusChange`, and the request types.
2. **Checks:** `in_scope`, `can_set_status` and `can_admit`, matching the summary's functions line for line.
3. **One function per operation** from the summary's Operations table, such as `admit`, `decline`, `appoint_successor`, `step_down`, `revoke`, `reinstate`, `clear_flag`, `move_member`, `close_group`, `close_church` and `hand_over_owner`. Each takes the actor, the targets and the relevant current state, and returns either:
   - a refusal with a reason code (for example `not_in_scope`, `target_not_below_actor`, `needs_voucher`, `no_successor`, `closed`), or
   - a **change set**: every field to update and every `StatusChange` row to add, so a caller can apply it in one transaction.
4. **Invariant check:** `check_invariants(state)` checks invariants 1 to 6 from the summary, so tests can verify the state after every operation.
5. **Allowed actions:** `allowed_actions(actor, target, state)` lists which operations the actor may perform on the target. The API will later serve this so web and mobile show only the buttons that work, without copying the rules.
6. **Capability questions:** `can_search`, `can_be_listed`, `can_vouch` and similar, so features ask what a person may do rather than reading their status.
7. **Storage port:** an interface for loading state and applying a change set, with an in-memory version for tests. The database version comes with the data model story.

## Acceptance criteria

1. **Checks match the doc.** Tests cover every row of the `settable` table and every early-return line of `canSetStatus` and `canAdmit`, each with a passing and a refused case.
2. **Every operation is covered.** Each row of the Operations table has a test for an allowed case and at least one refused case, and the refusal gives the expected reason code.
3. **Invariants hold.** After every allowed operation in the tests, `check_invariants` passes. A test that builds a state breaking each invariant shows `check_invariants` reports it, with one test named after each invariant.
4. **Succession is atomic.** An operation that ends someone's leadership returns the successor's appointment in the same change set, or closes the group or church. No change set leaves a group or church without a leader.
5. **History is always written.** Every change set that changes a status includes a matching `StatusChange` row with the right `kind`, `from`, `to` and `changedById`.
6. **Override rule.** A VERIFIER cannot undo a revocation or appointment made by an ADMIN or the OWNER. Tested both ways.
7. **No self-changes.** Nobody can change their own status through a status operation. Handing over the OWNER role and closing your own group are separate operations, tested separately.
8. **Pure logic.** The decision code imports nothing from the database layer or the web framework, and its tests run without a database, using the in-memory storage.
9. **Independence is enforced.** An import-contract check in CI, for example `import-linter`, fails if the rules module imports anything from the rest of the app.
10. **Capability questions.** `can_search`, `can_be_listed` and `can_vouch` are tested for every status, including REVOKED, PENDING and closed accounts.

## Out of scope

- Database tables, constraints and migrations for the new model, and the database storage adapter (a later story, after the specification is updated).
- Changing existing features to use the capability questions.
- API endpoints, including the allowed-actions endpoint, and web or mobile screens.
- Linking the new statuses to the stored `user_type` values.
- Notifications, such as telling a leader about a new applicant.
- Ordinary profile edits.

## Related

- [docs/verification.md](../docs/verification.md), especially the Data model summary
- [ADR-0016](../docs/adr/0016-church-trust-hierarchy-verification-model.md)
- Priority: Must have. Every later story that touches people, roles or membership depends on it.
