import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  apiError,
  json,
  makeMe,
  makePerson,
  mockApi,
  renderApp,
  signedInAs,
} from '../../../testUtils'

const ALL = 'GET /owner/contact-views?limit=50&offset=0'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }
const as = (status: string) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ status: status as 'owner' })),
})

const LENA = { id: 'lena', name: 'Lena Leader' }
const VIC = { id: 'vic', name: 'Vic Verifier' }
const FAY = { id: 'fay', name: 'Fay First' }
const SAM = { id: 'sam', name: 'Sam Second' }
const row = (id: string, viewer: typeof LENA, person: typeof FAY) => ({
  id,
  viewer,
  person,
  screen: 'person',
  viewed_at: '2026-11-12T08:30:00Z',
})
const ROWS = [row('v1', LENA, FAY), row('v2', VIC, SAM), row('v3', LENA, SAM)]
const owner = (extra = {}) => ({
  ...as('owner'),
  [ALL]: () => json(200, { items: ROWS, total: 3 }),
  ...extra,
})

describe('who sees the log', () => {
  it('shows the link and the page to the OWNER', async () => {
    signedInAs(makeMe(), owner())
    renderApp('/member/views')
    expect(await screen.findByText(/Lena Leader looked at the number of Fay First/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Number views' })).toHaveAttribute(
      'href',
      '/member/views',
    )
  })

  it.each(['admin', 'verifier', 'provider'])('sends an %s home', async (status) => {
    const api = signedInAs(makeMe(), {
      ...as(status),
      [ALL]: () => json(200, { items: ROWS, total: 3 }),
    })
    renderApp('/member/views')
    expect(await screen.findByText(/^Welcome/)).toBeVisible()
    expect(api.count(ALL)).toBe(0)
    expect(screen.queryByRole('link', { name: 'Number views' })).toBeNull()
  })

  it('sends a signed-out visitor to sign in', async () => {
    const api = mockApi({ [ALL]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/views')
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeVisible()
    expect(api.count(ALL)).toBe(0)
  })
})

describe('the log', () => {
  it('lists who looked at whom and when, and never a number', async () => {
    signedInAs(makeMe(), owner())
    renderApp('/member/views')
    const first = (
      await screen.findByText(/Lena Leader looked at the number of Fay First/)
    ).closest('li')!
    expect(within(first).getByText(/Nov 12|12 Nov|2026/)).toBeVisible()
    expect(screen.getByText(/deleted after 12 months/)).toBeVisible()
    expect(document.body.textContent).not.toMatch(/\+971/)
  })

  it('says a closed account is one, instead of leaving a gap', async () => {
    signedInAs(
      makeMe(),
      owner({
        [ALL]: () => json(200, { items: [row('v9', LENA, { id: 'gone', name: '' })], total: 1 }),
      }),
    )
    renderApp('/member/views')
    expect(await screen.findByText(/looked at the number of a closed account/)).toBeVisible()
  })

  it('narrows to one viewer, starting again from the first page, and clears', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        'GET /owner/contact-views?limit=50&offset=0&viewer_id=lena': () =>
          json(200, { items: [ROWS[0], ROWS[2]], total: 2 }),
      }),
    )
    renderApp('/member/views')
    const vic = (await screen.findByText(/^Vic Verifier looked at the number/)).closest('li')!
    expect(vic).toBeVisible()
    const first = screen.getByText(/Lena Leader looked at the number of Fay First/).closest('li')!
    await user.click(within(first).getByRole('button', { name: 'Only what Lena Leader looked at' }))
    expect(await screen.findByText(/Showing what Lena Leader looked at/)).toBeVisible()
    expect(screen.queryByText(/^Vic Verifier looked at the number/)).toBeNull()
    expect(api.count('GET /owner/contact-views?limit=50&offset=0&viewer_id=lena')).toBe(1)
    await user.click(screen.getByRole('button', { name: 'Show everything' }))
    expect(await screen.findByText(/^Vic Verifier looked at the number/)).toBeVisible()
  })

  it('narrows to one person, and to both together', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        'GET /owner/contact-views?limit=50&offset=0&person_id=sam': () =>
          json(200, { items: [ROWS[1], ROWS[2]], total: 2 }),
        'GET /owner/contact-views?limit=50&offset=0&viewer_id=lena&person_id=sam': () =>
          json(200, { items: [ROWS[2]], total: 1 }),
      }),
    )
    renderApp('/member/views')
    const second = (
      await screen.findByText(/Vic Verifier looked at the number of Sam Second/)
    ).closest('li')!
    await user.click(within(second).getByRole('button', { name: 'Only who looked at Sam Second' }))
    expect(await screen.findByText(/Showing who looked at Sam Second/)).toBeVisible()
    const third = screen.getByText(/Lena Leader looked at the number of Sam Second/).closest('li')!
    await user.click(within(third).getByRole('button', { name: 'Only what Lena Leader looked at' }))
    expect(await screen.findByText(/Showing what Lena Leader looked at/)).toBeVisible()
    expect(
      api.count('GET /owner/contact-views?limit=50&offset=0&viewer_id=lena&person_id=sam'),
    ).toBe(1)
  })

  it('goes back to the first page when the filter changes', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        [ALL]: () => json(200, { items: [ROWS[0]], total: 120 }),
        'GET /owner/contact-views?limit=50&offset=50': () =>
          json(200, { items: [ROWS[1]], total: 120 }),
        'GET /owner/contact-views?limit=50&offset=0&viewer_id=vic': () =>
          json(200, { items: [ROWS[1]], total: 1 }),
      }),
    )
    renderApp('/member/views')
    await screen.findByText(/^Lena Leader looked at the number/)
    await user.click(screen.getByRole('button', { name: 'Next' }))
    const second = (await screen.findByText(/^Vic Verifier looked at the number/)).closest('li')!
    await user.click(
      within(second).getByRole('button', { name: 'Only what Vic Verifier looked at' }),
    )
    expect(await screen.findByText(/Showing what Vic Verifier looked at/)).toBeVisible()
    expect(api.count('GET /owner/contact-views?limit=50&offset=0&viewer_id=vic')).toBe(1)
  })

  it('says when nobody has looked, and offers a retry when the log cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      owner({
        [ALL]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [], total: 0 }),
      }),
    )
    renderApp('/member/views')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Nobody has looked at a number.')).toBeVisible()
  })

  it('moves focus to the line that says what is shown, and back to the heading when cleared', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      owner({
        'GET /owner/contact-views?limit=50&offset=0&viewer_id=lena': () =>
          json(200, { items: [ROWS[0]], total: 1 }),
      }),
    )
    renderApp('/member/views')
    const first = (
      await screen.findByText(/^Lena Leader looked at the number of Fay First/)
    ).closest('li')!
    await user.click(within(first).getByRole('button', { name: 'Only what Lena Leader looked at' }))
    const line = await screen.findByText(/Showing what Lena Leader looked at/)
    expect(line).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Show everything' }))
    expect(
      await screen.findByRole('heading', { name: 'Who looked at phone numbers' }),
    ).toHaveFocus()
  })

  it('does not read a filter on one closed account as all closed accounts', async () => {
    const user = userEvent.setup({ delay: null })
    const gone = { id: 'gone', name: '' }
    signedInAs(
      makeMe(),
      owner({
        [ALL]: () => json(200, { items: [row('v9', gone, FAY)], total: 1 }),
        'GET /owner/contact-views?limit=50&offset=0&viewer_id=gone': () =>
          json(200, { items: [row('v9', gone, FAY)], total: 1 }),
      }),
    )
    renderApp('/member/views')
    await user.click(
      await screen.findByRole('button', { name: 'Only what a closed account looked at' }),
    )
    expect(await screen.findByText(/Showing what this closed account looked at/)).toBeVisible()
  })
})
