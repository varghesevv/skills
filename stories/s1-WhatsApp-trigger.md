# S1: Contact a provider on WhatsApp

## Story

As a **searcher**, I want to tap **Contact on WhatsApp** on a provider's profile, so that I can start a conversation with them straight away in the app I already use.

As an **admin**, I want each of those taps recorded, so that I can see which providers and skills are in demand without sending anyone's data to a third party.

## Background

Members already arrange work over WhatsApp. The site should not try to replace that conversation; it should hand the searcher over to WhatsApp and remember that the hand-over happened. This is the first signal we have that a search led to real contact with a provider.

The existing data model already holds each provider's `mobile_number` and `whatsapp_availability` (see [the data model](../docs/specification/03-data-model.md)). The specification still calls providers "freelancers".

## Depends on

- [S2: Activity events](s2-events.md), which adds the `events` table this story writes to.

## How it works

1. A signed-in, verified searcher opens a provider's profile, usually from a search for a skill.
2. If the provider has `whatsapp_availability = true`, the profile shows a **Contact on WhatsApp** button. Otherwise the button is not shown.
3. The button links to a site route, not straight to WhatsApp:

   ```
   GET /contact/<provider_id>?skill=<skill_id>
   ```

   `skill` is optional and is set when the searcher arrived from a search for that skill.
4. The route checks that the caller is a signed-in, verified member, writes a `whatsapp_click` event, and answers with an HTTP 302 redirect to:

   ```
   https://wa.me/<number>?text=<pre-filled message>
   ```

   - `<number>` is the provider's mobile number in international format, digits only (no `+`, spaces or leading zeros), as `wa.me` requires.
   - The pre-filled message is URL-encoded and names the skill when one is known, for example: *"Hi Priya, I found you on Fellowship Skills and I'm looking for help with plumbing."* Without a skill it reads: *"Hi Priya, I found you on Fellowship Skills."*
5. WhatsApp opens (app on mobile, WhatsApp Web on desktop) with the message ready for the searcher to edit and send.

The provider's number is never placed in the page itself, only in the redirect, so it cannot be scraped from profile pages.

## Recording the click

Each tap is recorded as a `whatsapp_click` event in the `events` table defined in [S2: Activity events](s2-events.md). The event holds the actor, provider, skill (if any), church and time. It never holds the phone number or the message text: we record that a click happened, not what was said.

The contact route loads no third-party analytics, pixels or trackers.

## Acceptance criteria

1. **Button shown correctly.** A verified searcher viewing a provider with WhatsApp availability sees **Contact on WhatsApp**. For a provider without WhatsApp availability, the button is absent.
2. **Redirect works.** Tapping the button sends the browser to `/contact/<provider_id>`, which returns a 302 to `https://wa.me/<number>?text=...` with the number in digits-only international format.
3. **Skill in the message.** When the searcher came from a search for a skill, the pre-filled message names that skill and the provider's first name. Without a skill, the generic message is used.
4. **Event recorded.** Each tap writes exactly one `whatsapp_click` row with actor, provider, skill (if any), church and timestamp filled in.
5. **Members only.** A visitor who is not signed in, or not yet verified, is sent to sign-in and no event is written and no number is revealed.
6. **Unavailable provider.** `/contact/<provider_id>` for a provider without WhatsApp availability, or one that does not exist or is suspended, returns 404 and writes no event.
7. **Number not exposed.** The provider's phone number does not appear in the profile page HTML or in any API response a searcher can call.
8. **No trackers.** The profile page and contact route load no third-party scripts and make no calls to third-party analytics services.
9. **Logging does not block contact.** If writing the event fails, the redirect still happens and the error is logged server-side.

## Out of scope, possible follow-up

- **"Did you use this provider?"** A few days after a `whatsapp_click`, ask the searcher whether they went ahead with the provider. A yes could feed a simple recommendation count on the provider's profile, and a no could optionally collect a reason. This needs its own story, covering timing, how the question is delivered, and how answers are shown.
- The `events` table itself, its privacy rules and other event types are in [S2](s2-events.md).
