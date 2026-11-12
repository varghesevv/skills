# 02 Functional requirements

These requirements follow the [verification rules](../verification.md) ([ADR-0016](../adr/0016-church-trust-hierarchy-verification-model.md)) and [ADR-0017](../adr/0017-authorisation-by-status.md). Where this file and the rules disagree, the rules win. A person has one account and one **status**, on a single ladder: REVOKED, PENDING, SEARCHER, PROVIDER, VERIFIER, ADMIN, OWNER. A higher status can do everything a lower one can. Words shown to people (searcher, provider, church, home group and the rest) come from the installation's terminology profile, not from this file. Choices the rules leave open are in the [decision log](../verification-decisions.md).

## Common (all people)

| ID | Requirement |
|---|---|
| FR-C-01 | A person MUST sign up with full name (2 to 200 characters), email, mobile number and password. Email and mobile number MUST each be unique among open accounts across the whole installation, revoked accounts included. |
| FR-C-02 | A person MUST log in with email and password and receive tokens (see API). There is one login for everyone; the token identifies the person only, and the status is read from the server on every request (ADR-0017). |
| FR-C-03 | A person MUST be able to reset a forgotten password through a one-time, expiring link sent by email. |
| FR-C-04 | Every login attempt (success or failure) MUST be recorded in login history. |
| FR-C-05 | Repeated failed logins MUST be throttled (default 5 failures per 15 minutes per email and IP). |
| FR-C-06 | A person MUST be able to view and edit only their own profile. Every profile has a name, email, mobile number, status, home group and the vouches received; the picture is an initials avatar for now. |
| FR-C-07 | `last_login_at` MUST be updated on successful login. |
| FR-C-08 | Before login, a client MUST be able to read the installation's words and the minimum and latest mobile app version from one public endpoint (`GET /api/v1/app/config`), so apps carry no copy of the word profiles. |
| FR-C-09 | A logged-in person MUST be able to list and download the published Android test builds of the mobile app, with version, build number, date, size, SHA-256 and release notes. Nobody who is not logged in can see or fetch them, there is no public file address, and each person has an hourly download limit (`DOWNLOAD_MAX_PER_HOUR`). |
| FR-C-10 | A person MUST be able to see their own status, home group, church and who set their status. |
| FR-C-11 | A person MUST be able to close their own account (see Leaving). A closed account is kept with the date it was closed, its personal details are cleared, and its history stays. |
| FR-C-12 | A person MUST receive an in-app notification for each event that concerns them (a new applicant for a leader, a vouch received, admission, revocation, a request to agree to a move or a handover, a re-check flag). |

## Joining

| ID | Requirement |
|---|---|
| FR-J-01 | Anyone MUST be able to sign up. The applicant MUST choose a church, then one of its home groups (each shown with its name and its leader's name), and whether they apply as a searcher or a provider. Sign-up is complete only when a group is chosen, so nobody is PENDING without a home group. The list of churches, groups and leader names is public (the sign-up screen has no account yet) and rate limited per IP; whether leader names should be hidden from anonymous callers is open (O-06). |
| FR-J-02 | Signing up through a home group's invitation link MUST select the church and the group automatically. |
| FR-J-03 | A new account starts as PENDING. The chosen group's leader MUST be notified. |
| FR-J-04 | While PENDING, an applicant MUST be able to choose a different church or group, or change what they apply for. The newly chosen leader is notified, and vouches already received still count. |
| FR-J-05 | A PENDING applicant can see the list of churches and their home groups with leaders, and nothing else. They are not searchable and cannot search. |
| FR-J-06 | Each applicant MUST get a vouch link to send to people who know them. Vouches are given only through that link. |
| FR-J-07 | Anyone admitted (SEARCHER or above) and not revoked MUST be able to vouch for an applicant, and to withdraw the vouch until the applicant is admitted. Nobody can vouch for themselves. Vouches by a revoked person no longer count for applicants still PENDING. |
| FR-J-08 | A verifier with authority over an applicant MUST be able to admit them once they have the vouches their role needs: for a SEARCHER, the leader's own sign-off; for a PROVIDER, the leader's sign-off and at least one live vouch from another admitted person in any church. The ADMIN's sign-off counts as the leader's for any group in the church. |
| FR-J-09 | A verifier MUST be able to decline an applicant. This closes the application like leaving: nobody is put on the revoked list, and the person may sign up again. |
| FR-J-10 | A SEARCHER MUST be able to apply to become a PROVIDER with the same vouches as a new provider applicant, using their vouch link, and keep searching meanwhile. |
| FR-J-11 | The link and invitation endpoints MUST resist guessing and flooding: long random tokens stored hashed, expiry, rate limits, and no sign of whether a link exists. |

## Verifier (VERIFIER, ADMIN and OWNER, within their scope)

A VERIFIER's scope is their home group (and people revoked from it), an ADMIN's is their church, and the OWNER's is everyone.

| ID | Requirement |
|---|---|
| FR-V-01 | A verifier MUST see the PENDING applicants in scope with their vouches, most-vouched first, the members, the revoked list, and anyone flagged for re-checking, prominently. |
| FR-V-02 | A verifier MUST be able to change the status of people in scope only within the limits of the rules: the OWNER anyone but themselves below OWNER; an ADMIN anyone in the church below ADMIN, from REVOKED to VERIFIER; a VERIFIER anyone in the group below VERIFIER, to REVOKED, SEARCHER or PROVIDER. Nobody changes their own status, except in a handover or when closing their own group. |
| FR-V-03 | A verifier MUST NOT override a revocation or leader appointment made by a higher verifier. |
| FR-V-04 | Every status change MUST be written to a permanent history with who made it, the old and the new status, and when. Each profile records who set its current status. |
| FR-V-05 | A verifier MUST be able to see the mobile numbers of people in scope on the verifier screens only. Each such view MUST be logged. Search results and provider pages never show a number. This is the one exception to the rule that only the reveal endpoint returns a number (decision D-07); who may see it, in which scope, whether PENDING applicants are included, the log content and any limits are fixed in the privacy part of [07](07-non-functional.md) (S1.4). |
| FR-V-06 | A verifier MUST be able to share an invitation link to their home group. |
| FR-V-07 | Revoking a person MUST remove them from their home group and any role, keep them on their church's revoked list with the group they were removed from, and block sign-up with their email or mobile number. If they led a group or a church, the successor is appointed in the same transaction. |
| FR-V-08 | Revoking a VERIFIER, ADMIN or OWNER MUST flag everyone whose current status that person set. Flagged people keep their access. A verifier at the revoked leader's level or higher MUST be able to re-confirm them, which clears the flag and makes the re-confirming verifier the new link in their chain of trust. |
| FR-V-09 | A revoked person MUST be reinstatable only by a verifier at the level of whoever revoked them or higher (a VERIFIER may reinstate someone they revoked from their own group), and reinstating places them in a home group. |

## Church structure and life cycle

| ID | Requirement |
|---|---|
| FR-L-01 | There MUST always be exactly one OWNER, one ADMIN per open church, and one leader per open home group, who belongs to that group. Nobody stops leading without a successor being appointed in the same transaction, or the group or church being closed in it (invariants 1 to 6 of the rules). |
| FR-L-02 | Any admitted member (SEARCHER or above) MUST be able to ask to start a home group. On the ADMIN's approval, in one transaction, the group is created, the member moves into it as its leader (VERIFIER unless higher), and a successor is named for the group they led. An ADMIN or the OWNER can start a group for themselves without approval. |
| FR-L-03 | An admitted member MUST be able to move to another group in the same church when the member, the leader of the group they join and the leader of the group they leave all agree. The ADMIN or OWNER can also move members. A leader moves only after stepping down through succession. |
| FR-L-04 | A leader MUST be able to step down, or be replaced, only with a successor from the group's members (PENDING or above). The person stepping down stays in the group as a PROVIDER (or SEARCHER if they prefer), recorded as set by the verifier above them, without flagging anyone. If nobody can succeed them and they stay, they keep the role. |
| FR-L-05 | An ADMIN or OWNER who leads their own group MUST be able to hand it on to another member and keep their status. |
| FR-L-06 | A group MUST be closable only once its leader is its last member; the leader closes it by moving into another group in the same transaction. Closed groups and churches are kept with the date closed, and nobody can join them. |
| FR-L-07 | Only the OWNER MUST be able to close a church other than their own. Closing it closes its groups and all its members' accounts (kept for history); nobody is revoked or flagged. The church's revoked list is kept. |
| FR-L-08 | The OWNER MUST be able to hand over to an ADMIN of another church: the OWNER names a new ADMIN for their own church and, if they lead their group, a new leader for it; the handover completes in one transaction when the chosen ADMIN accepts. The outgoing OWNER becomes a PROVIDER (or SEARCHER). |
| FR-L-09 | If the OWNER cannot hand over, the platform operators MUST be able to change the OWNER directly in the database with the same appointments; the change is recorded in the history as an operator change. |

## Leaving

| ID | Requirement |
|---|---|
| FR-X-01 | A PENDING applicant, SEARCHER or PROVIDER MUST be able to close their own account. They leave their group without being revoked, and nobody they admitted is flagged. |
| FR-X-02 | A VERIFIER or ADMIN MUST step down through succession before closing their account; the OWNER hands over first. A VERIFIER who is their group's only member closes the group instead. |
| FR-X-03 | Closed accounts MUST be kept, never deleted: the row stays with `closed_at` set, the personal fields are cleared, and the history keeps the ids of who changed what. The same flow is the in-app "delete account" the app stores require. |
| FR-X-04 | A person who has left MAY sign up again with the same email and mobile number; this creates a new account as PENDING. |

## OWNER and ADMIN

| ID | Requirement |
|---|---|
| FR-O-01 | When the first OWNER creates their profile, they MUST also name their church and their home group, which creates the first church with the OWNER as its ADMIN and the group's leader. |
| FR-O-02 | The OWNER MUST be able to create another church by inviting its ADMIN by email with the church's name. The church is created when the invitation is accepted. The invitee becomes ADMIN directly (set by the OWNER), names their own home group, and leads it. |
| FR-O-03 | The OWNER MUST be able to appoint or replace an ADMIN only through succession. |
| FR-O-04 | The OWNER MUST be able to manage labels (add, rename, deactivate). Labels in use MUST NOT be hard-deleted. |
| FR-O-05 | The OWNER and each ADMIN MUST be able to view the verification reports for their scope and the scheduled-run history, and trigger a report run and download its output (see [05](05-reports.md)). |
| FR-O-06 | OWNER actions are available on the web only. ADMIN and VERIFIER actions are available on the web and in the mobile app (decision D-11). This replaces the earlier rule that the platform administrator has no mobile access: the old platform admin is the OWNER, who stays web only. |

## Provider (PROVIDER and above)

| ID | Requirement |
|---|---|
| FR-P-01 | Maintain profile: full name, mobile number, WhatsApp availability (yes/no), nationality, primary language. |
| FR-P-02 | Set hourly rate, currency (ISO 4217) and whether the rate is negotiable. |
| FR-P-03 | Select labels: skills (each with a skill level), languages, timings, nativity. |
| FR-P-04 | Add, edit and delete unavailability periods (from < to). |
| FR-P-05 | View own ratings and comments. |
| FR-P-06 | View their home group, church and status, and who vouched for them. |
| FR-P-07 | A provider's public profile MUST NOT expose email or password data. A mobile number is never part of a profile or search response (see FR-M-06). The full name is shown to admitted searchers and above, never in the ratings a provider receives. |

## Searcher (SEARCHER and above)

| ID | Requirement |
|---|---|
| FR-M-01 | Search providers (see Search). Only admitted PROVIDERs and above are listed. |
| FR-M-02 | View a provider detail page: labels, rate, ratings, church and home group, availability. |
| FR-M-03 | Rate a provider 1-10 with an optional comment. One rating per rater and provider, editable (Q5). A person cannot rate themselves. |
| FR-M-04 | View ratings they have given. |
| FR-M-05 | Search results and the detail page MUST show a provider's mobile number greyed out (a placeholder, not the real number) with a Reveal button. |
| FR-M-06 | Reveal MUST ask the server for the number. On a phone or tablet it then opens the dialler (`tel:`); on a computer it shows the number. The number MUST NOT be in the page source, in any search or profile response, or in any browser cache. The only other place a number appears is the verifier screens (FR-V-05). |
| FR-M-07 | Every reveal MUST be recorded (who, whom, when, phone or computer, page, skills searched). Each person has an hourly and a daily limit (`REVEAL_MAX_PER_HOUR`, `REVEAL_MAX_PER_DAY`); beyond it the server answers `429` with `Retry-After`. |

## Search

| ID | Requirement |
|---|---|
| FR-S-01 | Filter by skill (any/all), skill level, language, timing, nativity. |
| FR-S-02 | Filter by maximum rate, currency and negotiable only. |
| FR-S-03 | Filter by availability on a given date range (excludes overlapping unavailability). |
| FR-S-04 | Filter by church or home group, and by minimum average rating. |
| FR-S-05 | Sort by rating, rate, newest. Results MUST be paginated. |
| FR-S-06 | Search MUST show only admitted providers (PROVIDER or above, not revoked, open) who have at least one skill, in any church. A rate and ratings are not required, so newcomers are listed. |
| FR-S-07 | Search at about 10 000 people and 4 000 providers MUST stay fast enough for interactive use (measured in S5.2). |
