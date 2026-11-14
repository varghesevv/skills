import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'

const LIST = 'GET /verifier/group-invitations'
const MAKE = 'POST /verifier/group-invitations'
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const row = (id: string, made: string, until: string) => ({
  id,
  created_at: `${made}T08:00:00Z`,
  expires_at: `${until}T08:00:00Z`,
})
const leader = () =>
  makePerson({ status: 'verifier', full_name: 'Lena Leader', leader: { name: 'Lena Leader' } })
// The links the server holds; a test changes them to what the server would answer next.
let held: unknown[] = []
const base = (items: unknown[] = []) => {
  held = items
  return {
    ...quiet,
    'GET /me': () => json(200, leader()),
    [LIST]: () => json(200, { items: held }),
  }
}
const token = () => `tok-${crypto.randomUUID()}`

describe('invitation links to my group', () => {
  it('shows the nav link to a leader of a group and not to one who does not lead theirs', async () => {
    signedInAs(makeMe(), base())
    const first = renderApp('/member/applicants')
    expect(await screen.findByRole('link', { name: /^Invite to my/ })).toBeVisible()
    first.unmount()
    signedInAs(makeMe(), {
      ...base(),
      'GET /me': () =>
        json(
          200,
          makePerson({ status: 'admin', full_name: 'Ada Admin', leader: { name: 'Lena Leader' } }),
        ),
    })
    renderApp('/member/applicants')
    await screen.findByRole('link', { name: /^Members/ })
    expect(screen.queryByRole('link', { name: /^Invite to my/ })).toBeNull()
  })

  it('makes a link, shows it once with the token only in the link, and copies it', async () => {
    const user = userEvent.setup({ delay: null })
    const secret = token()
    const api = signedInAs(makeMe(), {
      ...base(),
      [MAKE]: () => json(201, { id: 'i1', token: secret, expires_at: '2026-12-20T08:00:00Z' }),
    })
    renderApp('/member/invitations')
    await screen.findByText('No link works now.')
    held = [row('i1', '2026-11-20', '2026-12-20')]
    await user.click(screen.getByRole('button', { name: 'Make a link' }))
    const field = await screen.findByLabelText('Invitation link')
    expect((field as HTMLInputElement).value).toMatch(new RegExp(`/join/${secret}$`))
    expect(screen.getByText(/shown only now/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Copy the link' }))
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeVisible()
    expect(screen.getByTestId('invitation-i1')).toBeVisible()
    // No request address holds the token.
    expect(api.calls.some((c) => c.key.includes(secret))).toBe(false)
    expect(api.count(MAKE)).toBe(1)
  })

  it('lists the links that work and ends one', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...base([row('i1', '2026-11-10', '2026-12-10'), row('i2', '2026-11-12', '2026-12-12')]),
      'DELETE /verifier/group-invitations/i1': () => new Response(null, { status: 204 }),
    })
    renderApp('/member/invitations')
    await screen.findByTestId('invitation-i1')
    held = [row('i2', '2026-11-12', '2026-12-12')]
    await user.click(
      within(screen.getByTestId('invitation-i1')).getByRole('button', { name: 'End this link' }),
    )
    expect(await screen.findByText('The link no longer works.')).toBeVisible()
    expect(screen.queryByTestId('invitation-i1')).toBeNull()
    expect(screen.getByTestId('invitation-i2')).toBeVisible()
    expect(api.count('DELETE /verifier/group-invitations/i1')).toBe(1)
  })

  it('ending the link that was just made takes it off the screen', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...base(),
      [MAKE]: () => json(201, { id: 'i1', token: token(), expires_at: '2026-12-20T08:00:00Z' }),
      'DELETE /verifier/group-invitations/i1': () => new Response(null, { status: 204 }),
    })
    renderApp('/member/invitations')
    await screen.findByText('No link works now.')
    held = [row('i1', '2026-11-20', '2026-12-20')]
    await user.click(screen.getByRole('button', { name: 'Make a link' }))
    await screen.findByLabelText('Invitation link')
    held = []
    await user.click(screen.getByRole('button', { name: 'End this link' }))
    expect(await screen.findByText('The link no longer works.')).toBeVisible()
    expect(screen.queryByLabelText('Invitation link')).toBeNull()
  })

  it('ending another link leaves the one just made on the screen', async () => {
    const user = userEvent.setup({ delay: null })
    const secret = token()
    signedInAs(makeMe(), {
      ...base([row('i0', '2026-11-01', '2026-12-01')]),
      [MAKE]: () => json(201, { id: 'i1', token: secret, expires_at: '2026-12-20T08:00:00Z' }),
      'DELETE /verifier/group-invitations/i0': () => new Response(null, { status: 204 }),
    })
    renderApp('/member/invitations')
    await screen.findByTestId('invitation-i0')
    await user.click(screen.getByRole('button', { name: 'Make a link' }))
    await screen.findByLabelText('Invitation link')
    held = [row('i1', '2026-11-20', '2026-12-20')]
    await user.click(
      within(await screen.findByTestId('invitation-i0')).getByRole('button', {
        name: 'End this link',
      }),
    )
    await screen.findByText('The link no longer works.')
    expect((screen.getByLabelText('Invitation link') as HTMLInputElement).value).toContain(secret)
  })

  it('a failed ending does not stand next to the success of an earlier one', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...base([row('i1', '2026-11-10', '2026-12-10'), row('i2', '2026-11-12', '2026-12-12')]),
      'DELETE /verifier/group-invitations/i1': () => new Response(null, { status: 204 }),
      'DELETE /verifier/group-invitations/i2': () => apiError(500, 'server_error'),
    })
    renderApp('/member/invitations')
    await screen.findByTestId('invitation-i1')
    held = [row('i2', '2026-11-12', '2026-12-12')]
    await user.click(
      within(screen.getByTestId('invitation-i1')).getByRole('button', { name: 'End this link' }),
    )
    await screen.findByText('The link no longer works.')
    await user.click(
      within(screen.getByTestId('invitation-i2')).getByRole('button', { name: 'End this link' }),
    )
    expect(screen.queryByText('The link no longer works.')).toBeNull()
    expect(await screen.findByRole('alert')).toBeVisible()
  })

  it('making a link clears the notice of an earlier ending', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...base([row('i1', '2026-11-10', '2026-12-10')]),
      'DELETE /verifier/group-invitations/i1': () => new Response(null, { status: 204 }),
      [MAKE]: () => json(201, { id: 'i2', token: token(), expires_at: '2026-12-20T08:00:00Z' }),
    })
    renderApp('/member/invitations')
    await screen.findByTestId('invitation-i1')
    held = []
    await user.click(screen.getByRole('button', { name: 'End this link' }))
    await screen.findByText('The link no longer works.')
    await user.click(screen.getByRole('button', { name: 'Make a link' }))
    await screen.findByLabelText('Invitation link')
    expect(screen.queryByText('The link no longer works.')).toBeNull()
  })

  it('says so for a leader who handed their group on, when making a link', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), { ...base(), [MAKE]: () => apiError(409, 'no_home_group') })
    renderApp('/member/invitations')
    await screen.findByText('No link works now.')
    await user.click(screen.getByRole('button', { name: 'Make a link' }))
    expect(await screen.findByText(/do not lead a/)).toBeVisible()
  })

  it('says so when the list itself is refused for the same reason', async () => {
    signedInAs(makeMe(), { ...base(), [LIST]: () => apiError(409, 'no_home_group') })
    renderApp('/member/invitations')
    expect(await screen.findByText(/do not lead a/)).toBeVisible()
  })

  it('offers a retry when the links cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let failing = true
    signedInAs(makeMe(), {
      ...base(),
      [LIST]: () => (failing ? apiError(500, 'server_error') : json(200, { items: [] })),
    })
    renderApp('/member/invitations')
    const retry = await screen.findByRole('button', { name: 'Try again' })
    failing = false
    await user.click(retry)
    expect(await screen.findByText('No link works now.')).toBeVisible()
  })
})
