# Verification rules

> **Short on time, or an AI tool?** Read the [Data model summary](#data-model-summary) at the end first: types, invariants, permission checks and every operation, in one compact section. The prose below explains the reasons and is authoritative if the two ever disagree.

Skills is a closed, high-trust community that spans several sister organisations, such as a group of like-minded churches. Each church is an organisation in Skills. The churches are independent, but they let their members join one shared network, so that searchers can find providers across all of them.

Trust follows the shape of a church: the minister at the top, then the home group leaders, then the members of their groups. Every change to a person's status records who made it, so every member has a chain of trust that leads back to the top.

Accepted, 2026-11-12 ([ADR-0016](adr/0016-church-trust-hierarchy-verification-model.md)). These rules replace those agreed with the product owner on 2026-10-24.

## Context

- Expected scale: about 10,000 users, of whom at least 4,000 are providers.
- Churches do not keep a formal membership roll, so verification cannot rely on one. Trust comes from people who know each other instead.

## Structure

```
Skills ── always exactly 1 OWNER (authority over every church)
└── Church (organisation) ── always exactly 1 ADMIN
    └── Home group ── always exactly 1 leader, who belongs to it
        └── Members: SEARCHERs, PROVIDERs, and the leaders above
```

- **Every open, non-revoked person (PENDING or above) belongs to exactly one home group, and so to exactly one church.** This includes the VERIFIER, the ADMIN and the OWNER. A revoked person belongs to no home group, only to their church's revoked list.
- There is always exactly one OWNER. They belong to a home group in one church, usually the first, and **are always that church's ADMIN**: the OWNER is an ADMIN with platform-wide powers.
- **Every church always has exactly one ADMIN**, and is made up of home groups. The ADMIN is the person of ADMIN status in that church, or, in the OWNER's own church, the OWNER. The OWNER's church has no separate person of ADMIN status.
- **Every home group always has exactly one leader, who belongs to that group.** It can have any number of other members.
- These "always exactly one" rules hold because of [succession](#succession): nobody stops leading without a successor being appointed in the same step.
- The ADMIN can change the status of members of any home group in their church, so in any group both the ADMIN and the group's leader can do so.
- **Searching crosses church lines:** a searcher can find and hire providers in any church.

## Roles

| Role | Who, in church terms | Scope | What they do |
|---|---|---|---|
| **OWNER** | The person who set up Skills, usually the minister of the first church | The whole platform | Creates churches, appoints and replaces ADMINs, and can set anyone's status |
| **ADMIN** | The minister of a church | Their church | Approves new home groups, appoints successor leaders, and can admit or move members of any group in the church |
| **VERIFIER** | A home group leader | Their home group | Grows their group: invites people, admits them, and agrees moves in and out |
| **PROVIDER** | A member | Their home group | Lists their skills and services |
| **SEARCHER** | A member | Their home group | Finds providers for work they need doing |

A person holds one status at a time, and **a higher status includes everything the statuses below it can do.** So a PROVIDER can also search, and a VERIFIER, ADMIN or OWNER can also list their skills and services, and search. In the same way, an ADMIN or the OWNER can lead their own home group, and the OWNER is always the ADMIN of their own church.

### Verifiers

**Verifier** (lower case) means anyone who can change another person's status: a VERIFIER, an ADMIN or the OWNER. Verifiers have their own screen for managing status, alongside the member screens they also use. **VERIFIER** (capitals) means the home group leader status specifically.

## Statuses

From lowest to highest:

| Status | Meaning |
|---|---|
| **REVOKED** | A breach of trust. Removed from their home group and any role, and kept on their church's revoked list. No access, and fewer rights than PENDING: they cannot vouch or be vouched for. |
| **PENDING** | Signed up and waiting to be admitted. Every new account starts here. No access, except to see the list of churches and their home groups and leaders, so they can choose a group. |
| **SEARCHER** | Admitted as a searcher. Can search. |
| **PROVIDER** | Admitted as a provider. Can list skills and services, and search. |
| **VERIFIER** | Leader of a home group. Can also do everything a PROVIDER can. |
| **ADMIN** | Leader of a church. Can also do everything a VERIFIER can. |
| **OWNER** | Leader of the whole platform. Can also do everything an ADMIN can. |

## Who can change whose status

| Verifier | Can change | Can set |
|---|---|---|
| **OWNER** | Anyone except themselves | Any status below OWNER, including appointing or replacing a church's ADMIN. A new OWNER is only made by [handover](#owner-succession). |
| **ADMIN** | Anyone in their church below ADMIN | REVOKED up to VERIFIER |
| **VERIFIER** | Anyone in their home group below VERIFIER | REVOKED, SEARCHER, PROVIDER |

1. A verifier cannot override a revocation or a leader appointment made by a higher verifier. For example, a VERIFIER cannot reinstate someone an ADMIN revoked. Ordinary admissions (SEARCHER or PROVIDER) can be changed by any verifier with authority over that person, whoever made them.
2. Nobody can change their own status, except for the OWNER handing over (see [Owner succession](#owner-succession)) and a VERIFIER closing their group (see [Closing home groups and churches](#closing-home-groups-and-churches)).
3. Only the OWNER can create a church. A home group is started by a member with the ADMIN's approval (see [Starting a home group](#home-group-leaders)).
4. Only the church's ADMIN (or the OWNER) can appoint a home group's leader, and only as part of [succession](#succession) or approving a new group. Only the OWNER can appoint an ADMIN, in the same way. Anyone appointed as a leader must already exist in Skills, in any status from PENDING upwards.
5. An admitted member can move to another home group in the same church by agreement (see [Moving between groups](#home-group-leaders)), or be moved by the ADMIN (or the OWNER). Moving a group's leader out of it is a [succession](#succession): a successor is appointed in the same step. To change church, an admitted member leaves and signs up again in the new church, where different people know them.

### What verifiers can see

A VERIFIER sees the members of their home group, an ADMIN sees everyone in their church, and the OWNER sees everyone. Each also sees the revoked list for their scope (for a VERIFIER, the people revoked from their group), and anyone in that scope who is flagged for re-checking.

## History

1. Every status change is kept in a permanent history: who changed it, from what, to what, and when.
2. Each profile also records the verifier who set its current status. Following those links back gives the person's chain of trust.
3. The history is what [Revocation](#revocation) uses to find everyone a revoked leader admitted.

## Creating a church

1. **Setting up Skills.** When the OWNER creates their profile, they also give the name of their church and of their home group. This creates the first church, with that home group inside it. The OWNER is its first member, the group's leader and the church's ADMIN, so the church is complete from the start.
2. **Other churches.** To create a church, the OWNER invites its ADMIN by email, giving the church's name. The church is created when the invitation is accepted, so it never exists without an ADMIN.
3. The invited person signs up through the invitation and becomes the church's ADMIN directly, with the OWNER recorded as the verifier who set their status. They do not go through PENDING. As part of accepting, they give the name of their home group, which creates it with them as its first member and its leader.
4. Members then start the church's other home groups, with the ADMIN's approval (see [Home group leaders](#home-group-leaders)).

## Home group leaders

1. **A leader leads only the group they belong to.** A leader is anyone of VERIFIER status or higher, and each person leads at most one group: their own.
2. **Starting a home group.** Any admitted member of a church (SEARCHER or above) can ask to start a new home group, giving its name. When the ADMIN approves, in one step:
   - the group is created, and the member moves into it as its leader. They become a VERIFIER, unless they already hold a higher status;
   - if they led their old group, the ADMIN names a successor from that group's members, as in [Succession](#succession), or the old group closes if they were its only member.

   An ADMIN or the OWNER can start a group for themselves in the same way, without needing approval. This means groups grow from the bottom up, and the ADMIN only has to approve them.
3. **Growing a group.** A leader can share an invitation link to their group. People who sign up through it join that group as PENDING, and are admitted in the usual way.
4. **Moving between groups.** An admitted member can move to another home group in the same church when three people agree: the member, the leader of the group they are joining, and the leader of the group they are leaving. No ADMIN is needed. The ADMIN (or the OWNER) can also move members directly. A leader who wants to move steps down as group leader first, through [succession](#succession). An ADMIN or the OWNER [hands their group on](#succession) and keeps their status.

## Succession

**Nobody ever stops leading a group or a church without a successor being appointed in the same step.** This is what keeps exactly one OWNER, one ADMIN per church and one leader per group at all times.

1. **Successor for a group.** Whenever a group's leader stops leading it (stepping down, being moved, replaced or revoked, or a handover), the ADMIN (or the OWNER) appoints a new leader in the same step. The new leader must already be a member of that group, in any status from PENDING upwards (revoked people are no longer members). A PENDING member appointed this way becomes VERIFIER directly, without the usual vouches. If the group has no other member and the old leader is leaving it (revoked, moved or leaving Skills), the group is closed in the same step. A leader who is their group's only member and wants to stay in Skills steps down by [closing the group](#closing-home-groups-and-churches) instead.
2. **Successor for a church.** Whenever an ADMIN stops being ADMIN (stepping down, or being replaced or revoked), a new ADMIN is appointed in the same step. The new ADMIN must already be a member of that church, in any status from PENDING upwards, and becomes ADMIN directly, without the usual vouches. If they also lead a group, they keep leading it. If the church has no other member, it is closed in the same step.
3. **What happens to the person stepping down.** They stay in their own home group and become a PROVIDER (or a SEARCHER, if they prefer), without the usual vouches, because as a leader they could already provide. The change is recorded as set by the verifier above them, so the chain of trust stays unbroken, even when the step-down is self-initiated (a VERIFIER closing their own group is recorded as set by the church's ADMIN). That verifier can later change it like any ordinary admission. This is not a breach of trust, so nobody they admitted is flagged. (Revocation is different: see [Revocation](#revocation).)
4. **Handing a group on.** An ADMIN or the OWNER who leads their own group can appoint another member of it (PENDING or above) as its leader. They keep their own status.
5. **No successor available.** If a leader steps down while staying where they are, and nobody can succeed them, they keep that leadership role, with the matching status (VERIFIER for a group, ADMIN for a church), instead of becoming a PROVIDER. This mainly arises when the OWNER hands over while alone in their church or group.

| Situation | Who acts | Successor appointed in the same step |
|---|---|---|
| A VERIFIER steps down, or wants to leave | ADMIN | New leader for the group |
| A VERIFIER is moved to another group | ADMIN | New leader for the group they leave |
| A VERIFIER is replaced | ADMIN | The replacement |
| An ADMIN steps down, or wants to leave | OWNER | New ADMIN, and a new leader for any group they led |
| An ADMIN is replaced | OWNER | The replacement, and a new leader for any group they led |
| A leader is revoked | Whoever revokes them | As above for their role |
| The OWNER hands over | OWNER, then the new OWNER | See [Owner succession](#owner-succession) |

### Owner succession

1. **Planned handover.** The OWNER chooses an ADMIN to succeed them. They also name a new ADMIN for their own church, since they will no longer be its ADMIN, and a new leader for their own group if they lead it. The handover completes, in one step, when the chosen ADMIN accepts it. The new OWNER stays in their own home group and remains their own church's ADMIN, as every OWNER is, keeping any group they led.
2. The outgoing OWNER becomes a PROVIDER (or SEARCHER) in their home group, set by the new OWNER, as in [Succession](#succession).
3. **Fallback.** If the OWNER is unavailable and cannot hand over, or has breached trust, the platform operators change the OWNER directly in the database, outside the app. They make the same appointments in one change: a new OWNER from the ADMINs, a new ADMIN for the old OWNER's church, and a new leader for any group the old OWNER led. This is recorded in the history like any other status change.
4. An OWNER replaced for a breach of trust is REVOKED, as in [Revocation](#revocation), and the new OWNER clears the resulting flags.

## Closing home groups and churches

1. Closed groups and churches are kept, marked with the date they were closed, so the history and revoked lists that refer to them stay intact. Nobody can join a closed group or church.
2. A home group can only be closed once its leader is its last member. The other members move to other groups first, by agreement or by the ADMIN.
3. **The leader closes the group by transferring out.** The leader moves themselves into another home group in the same church. In one transaction they leave their group, the group is closed, and they join the other group:
   - a VERIFIER no longer leads a group, so they become a PROVIDER or a SEARCHER, as in [Succession](#succession);
   - an ADMIN or the OWNER keeps their status.
4. A group can also be closed as part of [succession](#succession), when its leader stops leading and it has no other member.
5. **Closing a church.** Only the OWNER can close a church, and not the one they belong to. Closing it closes the church and all its home groups, and closes all its members' accounts (they are [kept for history](#leaving)). This is not a breach of trust: nobody is revoked or flagged. Former members who want to stay in Skills sign up again, choosing another church and one of its home groups. The church's revoked list is kept, so revoked people still cannot sign up again.

## Joining

1. **Signing up.** Anyone can sign up. As part of signing up, the applicant:
   1. is shown the list of churches and selects one;
   2. is then shown the home groups in that church, each with its name and its leader's name, and selects one;
   3. chooses whether they are applying to be a searcher or a provider, so the leader knows which vouches they need.

   Signing up through a group's invitation link selects the church and group automatically.

   Sign-up is only complete once a group is selected, so nobody is ever PENDING without a home group. The applicant joins that group as PENDING, and its leader is sent a notification.
2. **Changing the choice.** While still PENDING, an applicant can choose a different church or group, or change what they are applying for. The newly chosen leader is notified, and any vouches already received still count.
3. Every profile has a picture, name, email, phone number, status, home group, the vouches received, and the ID of the verifier who set their current status (empty for new applicants).
4. **One account per person.** Email and phone number must each be unique among open accounts across all of Skills, so nobody can hold two accounts. Revoked accounts count as open, which is what stops a revoked person signing up again.
5. While someone is PENDING, others vouch for them. Anyone admitted (SEARCHER or above) and not REVOKED can vouch.
6. **Finding applicants.** PENDING applicants are not searchable. After signing up, an applicant gets a vouch link to send to people who know them, and vouches are given through that link.
7. A voucher can withdraw their vouch until the applicant is admitted.
8. The applicant's home group leader sees the group's PENDING applicants with their vouches, most-vouched first. The leader is expected to know the people in their group, so their decision to admit someone counts as a vouch.
9. A verifier can admit an applicant once they have the vouches their role needs:

| Applicant | Vouches needed | Then |
|---|---|---|
| **Searcher** | Just 1: their home group leader's own sign-off | Their home group leader admits them as SEARCHER |
| **Provider** | At least 2: 1 from their home group leader, and 1 from anyone else admitted, in any church | Their home group leader admits them as PROVIDER |

A searcher has a lighter check than a provider, because a provider is the role others rely on for work.

10. The church's ADMIN can also admit members of any home group in their church. The ADMIN's vouch then counts as the home group leader's.
11. **Declining.** If the leader does not know an applicant, they can decline the application. This closes it entirely, like [leaving](#leaving): nobody is put on the revoked list, and the person can sign up again later. If the applicant has simply chosen the wrong group, the leader can tell them instead, and they choose again while still PENDING.
12. **Searcher to provider.** An existing searcher who wants to become a provider needs the same vouches as a new provider applicant. They get a vouch link in the same way, and keep searching while they collect vouches. Their home group's leader (or the ADMIN or OWNER) admits them as a provider once they have the vouches, or declines the request. Declining a request only ends the request: the person stays a searcher, their vouch link stops working, the vouches stay on record and they are told; they may ask again. It is not a change of status, so it writes no history row, and nothing is closed.
13. Verifiers should be readily available, so applicants are not left waiting.

## Leaving

1. A PENDING applicant, a SEARCHER or a PROVIDER can close their own account. This is not a breach of trust: they are removed from their home group but not put on the revoked list, and nobody they admitted is flagged.
2. **Closed accounts are kept, not deleted.** A closed account is marked with the date it was closed and can no longer be used, but its history stays, so every chain of trust that runs through that person remains intact. The same applies to declined applications and to accounts closed when a church is closed.
3. **Leaders step down first.** A VERIFIER or ADMIN cannot close their account while they lead. They step down first, through [succession](#succession), and as a SEARCHER or PROVIDER they can then close their account. A VERIFIER who is their group's only member [closes the group](#closing-home-groups-and-churches) instead. The OWNER hands over (see [Owner succession](#owner-succession)).
4. Someone who has left can sign up again later with the same email and phone number. This creates a new account, as PENDING, like any new applicant.

## Revocation

1. Only a verifier can set a status to REVOKED, within the limits in [Who can change whose status](#who-can-change-whose-status). Revocation means a breach of trust, not someone simply leaving. The one exception is the OWNER, who can only be revoked by the platform operators (see [Owner succession](#owner-succession)).
2. A revoked person is removed from their home group and any role they held, and kept on their church's revoked list, with a record of the group they were removed from. If they led a group or a church, a successor is appointed in the same step (see [Succession](#succession)).
3. A revoked person cannot sign up again with the same email or phone number. Only a verifier at the same level as the one who revoked them, or higher, can reinstate them, and reinstating them means placing them in a home group again. A VERIFIER can reinstate someone they revoked from their own group, since they are best placed to make that judgement.
4. Revoking someone does not change anyone else's status. Instead, if the revoked person was a VERIFIER, ADMIN or OWNER, everyone whose current status they set is **flagged for re-checking**. Those people keep their access in the meantime.
5. The flag is cleared when a verifier at the revoked leader's level or higher re-confirms the person (or changes their status). For someone set by a revoked VERIFIER, that is the leader of the group they are now in, or the church's ADMIN. For someone set by a revoked ADMIN, it is the church's new ADMIN or the OWNER. For someone set by a revoked OWNER, it is the new OWNER. The re-confirming verifier is recorded as the new link in that person's chain of trust. Flags have no deadline, but flagged people are shown prominently on the verifier's screen until they are cleared.
6. Vouches given by a revoked person no longer count towards any applicant who is still PENDING.

## Why this design

- It mirrors how a church already works: the minister knows the home group leaders, and they know the people in their groups.
- Groups grow from the bottom up: members start groups and leaders bring people in and agree moves, while the layers above only approve. This keeps the load on ADMINs and the OWNER light.
- Every open, non-revoked person belongs to a home group, and the OWNER is simply an ADMIN with the widest scope.
- There is always exactly one OWNER, one ADMIN per church and one leader per group, because every succession happens in a single step.
- Every leader who steps down is treated the same way, so there are no special cases for handovers.
- Every admitted person has a recorded chain of trust that leads back to the OWNER.
- Requiring the home group leader's vouch for every provider keeps the higher-trust role tied to church leadership, while the second vouch adds an independent witness.
- Flagging rather than resetting on revocation means one bad appointment does not lock out every genuine member that person approved.

## Relation to the current specification

The [specification](specification/README.md) still describes organisations vouching for freelancers. These rules replace that model at the product level; the specification, data model and API need updating to match before the rules are built.

## Data model summary

A compact, typed restatement of the rules above, for quick reading by people and AI tools. If this summary and the prose ever disagree, the prose is authoritative.

### Types

```ts
// Ordered lowest → highest. A higher status can do everything a lower one can.
enum Status { REVOKED = 0, PENDING = 1, SEARCHER = 2, PROVIDER = 3, VERIFIER = 4, ADMIN = 5, OWNER = 6 }

type Id = string;

interface Church {
  id: Id;
  name: string;
  adminId: Id;                   // never null; the church's ADMIN, or the OWNER in the OWNER's own church
  closedAt: Date | null;         // set when the OWNER closes the church; kept for history and its revoked list
}

interface HomeGroup {
  id: Id;
  churchId: Id;
  name: string;
  leaderId: Id;                  // never null while open: succession always appoints a successor in the same step
  closedAt: Date | null;         // set when the group is closed; kept for history
}

interface Person {
  id: Id;
  name: string;
  email: string;                 // unique among open accounts across Skills (revoked accounts count as open)
  phone: string;                 // unique among open accounts across Skills
  closedAt: Date | null;         // set when the account is closed (leaving, declined, church closed); kept for history
  picture: string;
  status: Status;
  churchId: Id;                  // revoked people stay on this church's revoked list
  homeGroupId: Id | null;        // null if and only if status === REVOKED
  lastHomeGroupId: Id | null;    // set on revocation: the group they were removed from, so its leader keeps them in scope
  statusSetById: Id | null;      // who set the current status; null for new applicants, the first OWNER, and an OWNER appointed by the operators
  requestedStatus: Status.SEARCHER | Status.PROVIDER | null; // chosen at sign-up; also set when a searcher applies to provide
  flaggedForRecheck: boolean;    // set when whoever set their current status is revoked
}

interface Vouch {
  id: Id;
  applicantId: Id;               // a PENDING applicant, or a SEARCHER applying to be a PROVIDER
  voucherId: Id;                 // must be SEARCHER or above, and not REVOKED
  createdAt: Date;
  withdrawnAt: Date | null;      // can be withdrawn until the applicant is admitted
}

interface StatusChange {         // permanent history; the chain of trust is built from this
  id: Id;
  personId: Id;
  from: Status | null;           // null at account creation
  to: Status;
  changedById: Id | null;        // null only for an operator change in the database
  kind: "signup" | "admit" | "appoint" | "step-down" | "revoke" | "reinstate" | "reconfirm" | "handover" | "operator";
                                 // "reconfirm" clears a re-check flag: from === to, and the verifier becomes the new link in the chain
  at: Date;
}

interface AdminInvitation {      // the only invitation that creates a leader; the church is created on acceptance
  id: Id;
  email: string;
  churchName: string;            // the invitee names their own home group on accepting
  invitedById: Id;               // the OWNER
}

interface GroupRequest {         // a member asking to start a home group
  id: Id;
  requesterId: Id;               // SEARCHER or above, in the church
  churchId: Id;
  groupName: string;
  approvedById: Id | null;       // the ADMIN (or OWNER); on approval the group is created with the requester as leader
}

interface HandoverRequest {      // the OWNER proposes, the chosen ADMIN accepts; everything happens in one step on acceptance
  id: Id;
  ownerId: Id;                   // the outgoing OWNER
  newOwnerId: Id;                // an ADMIN of another church; stays ADMIN of their own church
  successorAdminId: Id | null;   // a member (PENDING or above) of the outgoing OWNER's church, becomes its ADMIN; null if nobody else is in the church
  successorLeaderId: Id | null;  // a member of the outgoing OWNER's group, if they lead it; null if nobody else is in the group
  // With no successor, the outgoing OWNER keeps that role: ADMIN of their church and/or leader of their group
  acceptedAt: Date | null;
}

interface MoveRequest {          // moving between groups by agreement, no ADMIN needed
  id: Id;
  personId: Id;                  // an admitted member who does not lead a group
  fromGroupId: Id;
  toGroupId: Id;                 // same church
  agreedByPerson: boolean;
  agreedByFromLeader: boolean;
  agreedByToLeader: boolean;     // the move happens when all three agree
}
```

### Invariants

1. Exactly one person has `status === OWNER`.
2. Every open person (`closedAt === null`) with `status !== REVOKED` has a `homeGroupId`, and that group's `churchId` equals the person's `churchId`.
3. Every open church (`closedAt === null`) has exactly one ADMIN: `Church.adminId` is the person in that church with `status === ADMIN`, or, in the OWNER's church, the OWNER (which then has no person with `status === ADMIN`). Every person with `status === ADMIN` is the ADMIN of their own church, and the OWNER is always the ADMIN of theirs.
4. Every open home group has exactly one leader: `HomeGroup.leaderId` is a person with `status >= VERIFIER` whose `homeGroupId` is that group. A person leads at most one group: their own.
5. Every person with `status === VERIFIER` is the leader of their own home group.
6. Any operation that ends someone's leadership of a group or church appoints the successor in the same transaction, or closes the group. A group's successor must already be a member of that group, and a church's successor a member of that church (`status >= PENDING`). If none exists, the group or church is closed in the same transaction if the old leader is leaving it; if they are staying, they keep the role with the matching status.

### Scope and permission check

```ts
// Who a verifier has authority over.
function inScope(actor: Person, target: Person): boolean {
  switch (actor.status) {
    case Status.OWNER:    return true;
    case Status.ADMIN:    return target.churchId === actor.churchId;
    case Status.VERIFIER: return (target.homeGroupId ?? target.lastHomeGroupId) === actor.homeGroupId; // includes people revoked from their group
    default:              return false;
  }
}

// The statuses each verifier may set. Setting VERIFIER or ADMIN only happens through
// approving a GroupRequest, a succession, or an AdminInvitation, which keep the invariants.
const settable: Record<number, Status[]> = {
  [Status.OWNER]:    [Status.REVOKED, Status.PENDING, Status.SEARCHER, Status.PROVIDER, Status.VERIFIER, Status.ADMIN],
  [Status.ADMIN]:    [Status.REVOKED, Status.PENDING, Status.SEARCHER, Status.PROVIDER, Status.VERIFIER],
  [Status.VERIFIER]: [Status.REVOKED, Status.SEARCHER, Status.PROVIDER],
};

function canSetStatus(actor: Person, target: Person, to: Status, last: StatusChange | null, lastBy: Person | null): boolean {
  if (target.closedAt !== null) return false;                     // closed accounts cannot be changed
  if (actor.id === target.id) return false;                       // never your own status (OWNER handover and closing a group are separate operations)
  if (target.status === Status.OWNER) return false;               // only operators can change the OWNER
  if (!inScope(actor, target)) return false;
  if (target.status >= actor.status) return false;                // only people below you
  if (!(settable[actor.status] ?? []).includes(to)) return false;
  // A revocation or leader appointment made by a higher verifier cannot be overridden.
  if (last && lastBy && (last.kind === "revoke" || last.kind === "appoint") && lastBy.status > actor.status) return false;
  return true;
}
```

### Admission requirements

```ts
// Live vouches = not withdrawn, and the voucher is not REVOKED.
// The admitting verifier's own sign-off counts as the home group leader's vouch.
function canAdmit(actor: Person, applicant: Person, to: Status.SEARCHER | Status.PROVIDER, liveVouches: Vouch[]): boolean {
  if (to === Status.SEARCHER) return applicant.status === Status.PENDING;
  // PROVIDER, from PENDING or SEARCHER: at least one live vouch from someone admitted, in any church, other than the admitting verifier.
  return liveVouches.some(v => v.voucherId !== actor.id);
}
```

The one exception: a VERIFIER, ADMIN or OWNER who steps down (in any [succession](#succession)) becomes a PROVIDER, or a SEARCHER if they prefer, without vouches.

### Operations

Every operation marked † appoints a successor in the same transaction (see [Succession](#succession)).

| Operation | Who | Effect |
|---|---|---|
| Set up Skills | First OWNER | Creates OWNER, first church and first home group, with the OWNER as the group's leader and the church's ADMIN |
| Create church | OWNER | Sends an `AdminInvitation`; the church is created when it is accepted |
| Accept ADMIN invitation | Invitee | Creates the church, the ADMIN, and a named home group they lead |
| Start home group † | Admitted member, approved by the ADMIN (an ADMIN or the OWNER for themselves, without approval) | `GroupRequest` approved: group created, requester moves in as leader (→ VERIFIER unless higher); successor for their old group if they led it |
| Invite to group | Group leader | Shares a link; people who sign up through it join the group as PENDING |
| Sign up | Anyone | Choose church, group, then searcher or provider (`requestedStatus`); creates PENDING person; notifies the group's leader |
| Change choice | PENDING applicant | Moves to another church or group, or changes `requestedStatus`; vouches kept; notifies new leader |
| Vouch / withdraw | SEARCHER or above, not REVOKED | Adds or withdraws a `Vouch` via the applicant's vouch link |
| Admit | Group leader, ADMIN, OWNER | PENDING → SEARCHER/PROVIDER, or SEARCHER → PROVIDER, if `canAdmit` |
| Decline | Group leader, ADMIN, OWNER | Sets `closedAt` on the application; not revoked; can sign up again |
| Apply to provide | SEARCHER | Sets `requestedStatus` to PROVIDER; status unchanged; notifies the group's leader; vouch link as for an applicant |
| Decline a provider request | Group leader, ADMIN, OWNER | Clears `requestedStatus` on a SEARCHER; status unchanged, no history row, nothing closed; the vouch link ends; notifies the person |
| Move member | Member + leader of the group they leave + leader of the group they join (`MoveRequest`), or the ADMIN / OWNER directly | Moves an admitted member to another group in the same church. Leaders step down as group leader first †; an ADMIN or the OWNER hands their group on and keeps their status. |
| Leave | PENDING, SEARCHER or PROVIDER | Sets `closedAt` (account kept for history); not revoked; nobody flagged; can sign up again as a new account. Leaders step down first †; the OWNER hands over |
| Step down / replace VERIFIER † | ADMIN, OWNER | Old VERIFIER → PROVIDER (or SEARCHER); successor, a member of the same group (PENDING or above) → VERIFIER; if no other member and the old leader is leaving the group, the group closes (otherwise they close it themselves) |
| Step down / replace ADMIN † | OWNER | Old ADMIN → PROVIDER (or SEARCHER); successor, a member of the same church (PENDING or above) → ADMIN; successor for any group they led; if no other member, the church closes |
| Hand group on | ADMIN or OWNER leading their own group | Appoints another member of it (PENDING or above) as leader; keeps own status |
| Revoke † | Verifier (OWNER: operators only) | → REVOKED; `homeGroupId = null`, `lastHomeGroupId` set; successor for any group or church they led; anyone whose current status they set is flagged; their vouches stop counting for PENDING applicants |
| Reinstate | Verifier at the revoker's level or higher | REVOKED → a status and a home group |
| Clear flag | Verifier at the revoked leader's level or higher | Re-confirms (a `"reconfirm"` history entry) or changes status; becomes the new `statusSetById` |
| Hand over OWNER † | OWNER proposes a `HandoverRequest`, the chosen ADMIN accepts | Chosen ADMIN → OWNER, still ADMIN of their own church; old OWNER → PROVIDER (or SEARCHER); successor ADMIN for the old OWNER's church; successor leader for any group the old OWNER led. With no possible successor, the old OWNER keeps that role (→ ADMIN) |
| Operator change † | Platform operators | Same appointments as a handover, for an unavailable or untrustworthy OWNER; if breach, old OWNER → REVOKED |
| Close group | The group's leader, once they are its last member | One transaction: leader moves to another group in the church, group's `closedAt` is set; a VERIFIER → PROVIDER (or SEARCHER), recorded as set by the ADMIN; an ADMIN or OWNER keeps their status |
| Close church | OWNER, not for their own church | Sets `closedAt` on the church, its groups and all its members' accounts (all kept for history); nobody revoked or flagged; members can sign up again elsewhere; the revoked list is kept |
