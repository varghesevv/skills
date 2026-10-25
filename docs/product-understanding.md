# Product understanding

Status: draft for discussion. Revise freely; add a line to the revision log at the end.

This page records what Skills is for, who the actors are, and how they should be named. It is written
from the project owner's goals and from a note shared by a team member. Private details of that note
(organisation names, pricing ideas, domain and legal worries) are deliberately **not** copied here,
because this repository is public.

## 1. Goals

1. **Open source.** Anyone can download it and run their own instance.
2. **For communities.** An instance can be closed (a church group, an alumni circle, a neighbourhood)
   or an open platform.
3. **A marketplace for skills.** People with a skill offer it; people who need work done look for
   them, for short or mid term work.
4. **Trust first.** Introductions are only valuable if people can trust who they meet.
   Trust comes from verification: someone known to the community vouches for a person.
5. **Configurable per instance.** Because communities differ, an instance chooses its own words and
   its own rules (see section 5).

## 2. The exchange in one picture

```
 Verifier ──vouches for──▶ Skill Provider ◀──searches / rates── Skill Seeker
 (membership, trust)       (offers a skill)                      (needs a job done)
                      Administrator approves who may take part
```

Three roles plus an administrator:

| Working name | What the person does | Team note calls it | In the app and API today |
|---|---|---|---|
| Skill Provider | Lists skills, experience, rate and availability; is found and hired | Provider | `freelancer` |
| Skill Seeker | Searches for providers, contacts them, rates them after work | Searcher | `workhost` |
| Verifier | Confirms that a person is a genuine member and vouches for them | Verifier | `organisation` |
| Administrator | Approves registrations, manages labels and reports | (not named) | `admin` |

The stored names (`freelancer`, `workhost`, `organisation`) never change with the wording shown on
screen. Only the display words are configurable.

> **Mix-up to fix.** The current `church` wording profile shows Freelancer as "Searcher" and Work
> host as "Provider". By the team note's definitions it is the other way round: the person offering a
> skill is the Provider and the person needing work is the Searcher. This needs correcting once the
> names in section 4 are agreed.

## 3. Where the team note and the current app differ

| Topic | Team note | Current app | To decide |
|---|---|---|---|
| Who verifies | Verifiers are people; they verify providers, searchers and other verifiers (a chain of trust) | Organisations vouch for freelancers only; the administrator approves organisations | Person-level verifiers? Verifying seekers? Chain of trust? |
| Seekers must be verified | Yes | Work hosts register and use the system without a vouch | Per-instance rule |
| Provider verified "to a higher degree" | Possibly | One level (vouch: pending, approved, revoked) | Verification levels |
| Photos | Required for providers and seekers | No photo | Add, as an instance setting |
| Feedback score | Future | Ratings 1 to 10 exist | Already built |
| Closed to outsiders | Yes, for that community | Registration is open; the administrator approves | Open or closed mode per instance |
| Contact tracking | Reveal the phone number on request to estimate demand | Contact details are not shown in search | "Reveal contact" action with a count |
| Browse by sector | Drill-down tree (education, medical, legal, IT, ...) plus free text for seekers | Skill labels and filters | Sector tree on top of labels |
| First version data | One table, loaded from a CSV file | Full database, demo data generator | CSV import for small communities? |
| Notifications, messaging | App, later version | Not built (mobile app plan exists) | Later |

## 4. Naming the actors

### The problem
"Searcher", "Provider" and "Verifier" are too generic. Each leaves the obvious question open:
searcher of what, provider of what, verifier of what? "Searcher" is the worst case in this app: it
reads as the person who runs searches, yet in a search the person with a skill is the one who is
searched for.

### Rule
A name should say **what the person does and to what**, from the point of view of the exchange (offer
a skill, seek a skill, verify membership), and should not fit another role.

### Suggested default names
| Role | Suggested | Why | Other candidates |
|---|---|---|---|
| Offers a skill | **Skill Provider** | Says what is provided; cannot be confused with the seeker | Skilled Member, Practitioner, Helper |
| Needs a job done | **Skill Seeker** | Mirrors "Skill Provider": the direction is clear | Requester, Client, Hirer |
| Confirms membership | **Member Verifier** | Says what is verified (that the person is a real member), not their skill | Endorser, Sponsor, Elder, Referee |

Names that say what is exchanged are easier to explain than abstract ones, but a community's own words
usually communicate best (next table).

### Examples per kind of community
| Community | Offers a skill | Needs a job done | Verifies |
|---|---|---|---|
| Open marketplace | Freelancer | Client | Verifier |
| Church group | Skilled member | Member in need | Church (or Elder) |
| Alumni circle | Alumni expert | Alumni client | Alumni chapter |
| Neighbourhood | Neighbour helper | Neighbour | Residents' association |

### Statement for the shared document
> Searcher, Provider and Verifier are too generic: each leaves the question open of what is searched,
> provided or verified. In the app "Searcher" is also confusing, because the person with the skill is
> the one being searched for. I suggest naming each actor by what they do in the exchange: **Skill
> Provider** (offers a skill as a service), **Skill Seeker** (needs a job done) and **Member
> Verifier** (confirms someone is a genuine member). A community can then use its own words, for
> example "Skilled member / Member in need / Elder" for a church group. Please also note that our
> current church wording has Provider and Searcher the wrong way round compared with the definitions
> in this document; we will correct it once the names are agreed.

## 5. Making it configurable per instance

What exists today (`frontend/src/terminology/profiles.json`, chosen by `TERMINOLOGY_PROFILE`):
the words for the three roles (singular and plural), the web address words, and the small label
above the menu (role badge).

What this page suggests adding, each as an instance setting with a safe default:

| Setting | Values |
|---|---|
| Description of each role (one sentence, shown on registration) | Text per profile |
| Open or closed instance | Open registration, or invitation/verification required |
| Who must be verified before taking part | None, providers, providers and seekers |
| Photo required | No, providers, providers and seekers |
| Sector tree (browse by sector) | List of sectors per instance |
| Reveal contact details on request | On or off |

Settings that change behaviour need the specification and an architecture decision record when they
change how the system is built (see CONTRIBUTING).

## 6. Open questions

1. Final names for the three roles (section 4), and whether the default words in the open source
   release should be the generic ones or the descriptive ones.
2. Can a person be a verifier, or only an organisation? Can a verifier be verified (chain of trust)?
3. Do seekers need verification in every instance?
4. Is a contact "reveal" acceptable for privacy, and what is stored about it?
5. Is a CSV-loaded small instance a supported way to start?

## Revision log
- 2026-10-26: first draft from the owner's goals and the team note.
