# S2: Activity events

## Story

As an **admin**, I want key activity on the site recorded in one place, so that I can see which providers and skills are in demand and how members find each other, without sending anyone's data to a third party.

## Background

Several features need to record that something happened: a searcher contacting a provider on WhatsApp ([S1](s1-WhatsApp-trigger.md)), searches, profile views and vouches. Rather than a table per feature, this story adds one general `events` table that each feature writes to.

## Events table

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| type | text NOT NULL | One of `search`, `profile_view`, `whatsapp_click`, `vouch`. Enforced with a CHECK constraint or enum so new types are added deliberately. |
| actor_id | uuid FK → users, NULL | The member who did it. NULL only for system events. |
| provider_id | uuid FK → providers, NULL | The provider the event is about, where there is one. |
| skill_id | uuid FK → skills, NULL | The skill involved, where known. |
| church_id | uuid FK → churches, NULL | The actor's church at the time, so reports stay correct if someone moves church. |
| created_at | timestamptz NOT NULL default now() | |
| metadata | jsonb NOT NULL default '{}' | Type-specific detail, for example the search query or the referring page. Never phone numbers, message text or other contact details. |

Indexes on `(type, created_at)` and `(provider_id, created_at)`.

The specification calls providers "freelancers"; the foreign key points at whichever table holds them (see [the data model](../docs/specification/03-data-model.md)).

## Event types

| Type | Written when | Story |
|---|---|---|
| `whatsapp_click` | A searcher taps Contact on WhatsApp | [S1](s1-WhatsApp-trigger.md) |
| `search` | A member runs a skill search | Later story |
| `profile_view` | A member opens a provider's profile | Later story |
| `vouch` | A member vouches for an applicant | Later story |

## Privacy

- Events are visible to **admins only**. Providers, searchers, vouchers and verifiers cannot read them, through the UI or the API.
- No third-party analytics, pixels or trackers. Everything stays in our own database.
- Events record that something happened, not the content of any conversation.

## Acceptance criteria

1. **Table exists.** A reversible migration creates the `events` table with the columns, constraint and indexes above.
2. **Types enforced.** Inserting an event with a type outside the allowed list fails.
3. **Simple to write.** The backend has one helper for recording an event, which features such as S1 call.
4. **Admin only.** Only admins can list or read events. Any other role gets 403 from the events API.
5. **Filterable.** Admins can list events filtered by type, provider, church and date range, newest first, paginated.
6. **No contact details.** No event stores a phone number or message text, in a column or in `metadata`.
7. **No trackers.** No event data is sent to any third-party service.

## Out of scope

- Writing `search`, `profile_view` and `vouch` events (each comes with its own story).
- An admin report or dashboard over the events table.
- Retention and deletion rules for old events.
