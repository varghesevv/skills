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

const CHURCHES = 'GET /owner/churches?limit=50&offset=0'
const INVITES = 'GET /owner/churches/invitations?limit=50&offset=0'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }
const as = (status: string) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ status: status as 'owner' })),
})
const owner = (extra = {}) => ({
  ...as('owner'),
  [CHURCHES]: () => json(200, { items: [], total: 0 }),
  [INVITES]: () => json(200, { items: [], total: 0 }),
  ...extra,
})

const OWN = {
  id: 'church-1',
  name: 'Grace Church',
  admin_name: 'Olive Owner',
  open: true,
  groups: 3,
  members: 40,
  revoked: 2,
  closed_at: null,
}
const HOPE = {
  id: 'church-2',
  name: 'Hope Church',
  admin_name: 'Ada Admin',
  open: true,
  groups: 1,
  members: 9,
  revoked: 0,
  closed_at: null,
}
const OLD = {
  ...HOPE,
  id: 'church-3',
  name: 'Old Church',
  open: false,
  closed_at: '2026-10-01T08:00:00Z',
}

describe('who sees the churches', () => {
  it('shows the link and the page to the OWNER only', async () => {
    signedInAs(makeMe(), owner({ [CHURCHES]: () => json(200, { items: [OWN], total: 1 }) }))
    renderApp('/member/churches')
    expect(await screen.findByRole('heading', { name: 'Grace Church' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Organisations' })).toHaveAttribute(
      'href',
      '/member/churches',
    )
  })

  it.each(['admin', 'verifier', 'provider'])('sends an %s home', async (status) => {
    const api = signedInAs(makeMe(), {
      ...as(status),
      [CHURCHES]: () => json(200, { items: [OWN], total: 1 }),
      [INVITES]: () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/churches')
    expect(await screen.findByText(/^Welcome/)).toBeVisible()
    expect(api.count(CHURCHES)).toBe(0)
    expect(screen.queryByRole('link', { name: 'Churches' })).toBeNull()
  })

  it('sends a signed-out visitor to sign in', async () => {
    const api = mockApi({ [CHURCHES]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/churches')
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeVisible()
    expect(api.count(CHURCHES)).toBe(0)
  })
})

describe('the list of churches', () => {
  it('shows each church with its ADMIN and its counts, and closes only the others', async () => {
    signedInAs(
      makeMe(),
      owner({ [CHURCHES]: () => json(200, { items: [OWN, HOPE, OLD], total: 3 }) }),
    )
    renderApp('/member/churches')
    const own = (await screen.findByRole('heading', { name: 'Grace Church' })).closest('li')!
    expect(within(own).getByText(/3 home groups, 40 members, 2 revoked/)).toBeVisible()
    expect(within(own).getByText(/Yours/)).toBeVisible()
    expect(within(own).queryByRole('button')).toBeNull()
    const hope = screen.getByRole('heading', { name: 'Hope Church' }).closest('li')!
    expect(within(hope).getByText(/Ada Admin/)).toBeVisible()
    expect(within(hope).getByRole('button', { name: 'Close Hope Church' })).toBeVisible()
    const old = screen.getByRole('heading', { name: 'Old Church' }).closest('li')!
    expect(within(old).getByText(/Closed/)).toBeVisible()
    expect(within(old).queryByRole('button')).toBeNull()
  })

  it('asks first, closes the church and says what was closed', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        [CHURCHES]: () => json(200, { items: [OWN, HOPE], total: 2 }),
        'POST /owner/churches/church-2/close': () =>
          json(200, { id: 'church-2', name: 'Hope Church', closed_groups: 1, closed_accounts: 9 }),
      }),
    )
    renderApp('/member/churches')
    await user.click(await screen.findByRole('button', { name: 'Close Hope Church' }))
    expect(api.count('POST /owner/churches/church-2/close')).toBe(0)
    expect(screen.getByText(/It cannot be undone/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(
      await screen.findByText('Hope Church is closed: 1 home groups and 9 accounts.'),
    ).toBeVisible()
    expect(api.count('POST /owner/churches/church-2/close')).toBe(1)
  })

  it('puts a refusal to close the own church in words', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      owner({
        [CHURCHES]: () => json(200, { items: [HOPE], total: 1 }),
        'POST /owner/churches/church-2/close': () => apiError(409, 'owner_church'),
      }),
    )
    renderApp('/member/churches')
    await user.click(await screen.findByRole('button', { name: 'Close Hope Church' }))
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot close your own/)
  })

  it('can be cancelled at the question, and shows a refusal in words', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      owner({
        [CHURCHES]: () => json(200, { items: [OWN, HOPE], total: 2 }),
        'POST /owner/churches/church-2/close': () => apiError(409, 'state_changed'),
      }),
    )
    renderApp('/member/churches')
    await user.click(await screen.findByRole('button', { name: 'Close Hope Church' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Close Hope Church' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Close Hope Church' }))
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/changed meanwhile/)
  })

  it('says when there are none, and offers a retry when the list cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      owner({
        [CHURCHES]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [], total: 0 }),
      }),
    )
    renderApp('/member/churches')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No organisations yet.')).toBeVisible()
  })
})

describe('invite the ADMIN of a new church', () => {
  const fill = async (user: ReturnType<typeof userEvent.setup>, name: string, email: string) => {
    await user.type(await screen.findByLabelText(/^Name of the/), name)
    await user.type(screen.getByLabelText(/^Email address of the/), email)
  }

  it('sends the name and address and shows the link once, with the token only in the link', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        'POST /owner/churches': () =>
          json(201, { id: 'i1', token: 'tok-abcdefghij', expires_at: '2026-11-28T08:00:00Z' }),
      }),
    )
    renderApp('/member/churches')
    await fill(user, ' Hope Church ', 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    expect(await screen.findByText(/shown only now/)).toBeVisible()
    expect(screen.getByLabelText('Invitation link')).toHaveValue(
      `${window.location.origin}/invite/tok-abcdefghij`,
    )
    expect(api.calls.find((c) => c.key === 'POST /owner/churches')?.body).toEqual({
      church_name: 'Hope Church',
      email: 'ada@example.com',
    })
    // The fields are empty again.
    expect(screen.getByLabelText(/^Name of the/)).toHaveValue('')
    await user.type(screen.getByLabelText(/^Name of the/), 'Next Church')
    await user.type(screen.getByLabelText(/^Email address of the/), 'next@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    expect(await screen.findByLabelText('Invitation link')).toBeVisible()
  })

  it('keeps the link of the first invitation when the second one is refused', async () => {
    const user = userEvent.setup({ delay: null })
    let calls = 0
    signedInAs(
      makeMe(),
      owner({
        'POST /owner/churches': () =>
          ++calls === 1
            ? json(201, { id: 'i1', token: 'tok-first-0001', expires_at: '2026-11-28T08:00:00Z' })
            : apiError(409, 'account_exists'),
      }),
    )
    renderApp('/member/churches')
    await fill(user, 'Hope Church', 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    await screen.findByLabelText('Invitation link')
    await fill(user, 'Next Church', 'next@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/belongs to an account already/)
    expect(screen.getByLabelText('Invitation link')).toHaveValue(
      `${window.location.origin}/invite/tok-first-0001`,
    )
  })

  it('keeps the button off until both fields are filled', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), owner())
    renderApp('/member/churches')
    const submit = await screen.findByRole('button', { name: 'Create the invitation' })
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText(/^Name of the/), 'Hope Church')
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText(/^Email address of the/), 'ada@example.com')
    expect(submit).toBeEnabled()
  })

  it.each([
    ['church_name_taken', 409, /with this name exists already/],
    ['invitation_exists', 409, /invitation for this .* or address already/],
    ['account_exists', 409, /belongs to an account already/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), owner({ 'POST /owner/churches': () => apiError(status, code) }))
    renderApp('/member/churches')
    await fill(user, 'Hope Church', 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })
})

describe('invitations waiting', () => {
  const WAITING = {
    id: 'i1',
    church_name: 'Hope Church',
    email: 'ada@example.com',
    created_at: '2026-11-10T08:00:00Z',
    expires_at: '2026-11-24T08:00:00Z',
    expired: false,
  }

  it('lists them, marks an expired one, and cancels one', async () => {
    const user = userEvent.setup({ delay: null })
    let cancelled = false
    const api = signedInAs(
      makeMe(),
      owner({
        [INVITES]: () =>
          json(200, {
            items: cancelled
              ? []
              : [WAITING, { ...WAITING, id: 'i2', church_name: 'Stale Church', expired: true }],
            total: cancelled ? 0 : 2,
          }),
        'DELETE /owner/churches/invitations/i1': () => {
          cancelled = true
          return json(204)
        },
      }),
    )
    renderApp('/member/churches')
    const row = (await screen.findByText(/Hope Church, for ada@example.com/)).closest('li')!
    expect(within(row).getByText(/Until/)).toBeVisible()
    expect(screen.getByText(/Expired/)).toBeVisible()
    await user.click(
      within(row).getByRole('button', { name: 'Cancel the invitation for Hope Church' }),
    )
    expect(await screen.findByText('The invitation was cancelled.')).toBeVisible()
    expect(api.count('DELETE /owner/churches/invitations/i1')).toBe(1)
  })

  it('says when none are waiting', async () => {
    signedInAs(makeMe(), owner())
    renderApp('/member/churches')
    expect(await screen.findByText('No invitations are waiting.')).toBeVisible()
  })
})
