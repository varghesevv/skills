# Store data-safety answers (Google Play) and privacy labels

Status: written 2026-11-16 (S9.2) for the first release that has chat. **Check each answer against the app and the privacy statement (`/privacy`) when the form is filled in, and again at every release that changes what is collected.** The privacy statement is the text people read; this page is what to answer in the store forms so that the two say the same.

The app has no advertising and no analytics tools, no location, no contacts, no camera or microphone and no files. Sign-in uses the person's own account on the Skills server (not a third-party login).

## Google Play, "Data safety" form

**Does the app collect or share data?** Yes, it collects data. **Is all data encrypted in transit?** Yes (HTTPS and `wss` only; cleartext is off in the manifest). **Can people ask for their data to be deleted?** Yes: in the app (Account, Leave) and on the web (My account); closing the account removes the personal details at once. The privacy statement says what remains (statuses, vouches, ratings, without personal details).

| Data type (Play's wording) | Collected | Shared | Why | Optional | Notes |
|---|---|---|---|---|---|
| Name | Yes | No | App functionality, account management | No | Shown to people in the same church and to people they write to. |
| Email address | Yes | No | Account management | No | Never shown to other members. |
| Phone number | Yes | No | App functionality | No | Shown only to a person who presses Reveal on a provider's page and to the leaders of the person's own group and church; every view is recorded. |
| User IDs | Yes | No | App functionality, account management | No | An internal id; no advertising id is read. |
| Messages: other in-app messages | Yes | No | App functionality | No | The text of chat messages, with who wrote them and when. Seen by the two people only; the OWNER can read a conversation that someone reported (each reading is recorded). Kept until both people close their accounts. |
| Device or other IDs | Yes | Yes (see below) | App functionality (notifications) | Yes | The Firebase address of the phone, only if the person allows notifications. Removed at sign-out and when the account is closed. |
| App interactions / Diagnostics | No | No | | | No analytics, no crash reporting service. Sign-in attempts are recorded on the server for security (time, result, network address, browser), kept 12 months. |
| Location, Contacts, Photos and videos, Audio, Files, Health, Financial info, Web browsing | No | | | | |

**Shared with third parties?** The only third party is Google's Firebase Cloud Messaging, which carries a notification to the phone. It receives the phone's address and a notice that says only "You have a new message" and the id of the conversation: no message text and no name. Play's form treats data handled by a service provider on the app's behalf as not "shared" when it is only used to provide the service; answer "No" for sharing and describe the notification in the privacy statement (it does). If Google's guidance on this changes, answer "Yes" for "Device or other IDs" and state the purpose "App functionality".

**Security practices:** data is encrypted in transit; people can request deletion (above); the app follows Play's Families policy only if it is later offered to children (it is not: sign-up is for adults of a church).

## Content rating and other forms

- **Target audience:** adults (church members). No ads. No purchases.
- **User-generated content (chat):** Play requires a way to report it and to block people: the app has "Report" and "Block" in every conversation (S8.7), and a person who is blocked is not told. State that the OWNER reviews reports (privacy statement and the runbook). Add the support address when the account is created.
- **Account deletion:** the form asks for a web address where a person can ask for deletion: use the Privacy page (`/privacy`), which says how (My account, Close your account), and name the in-app path.
- **App access for the reviewer:** give a demo sign-in (a searcher and a provider on the demo server) in the form's "App access" section. The accounts are created by the OWNER with the runbook's command; never put real people's details there.

## Apple privacy labels (when the iPhone app exists)

The same table applies: Contact info (name, email, phone number), User content (messages), Identifiers (user id, device token), all "linked to the user", none used for tracking.
