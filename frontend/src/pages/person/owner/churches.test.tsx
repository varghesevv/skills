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

// Made at run time: no token-like text is kept in the source (ADR-0011).
const FIRST = `link-${crypto.randomUUID()}`

const OWN = {
  id: 'church-1',
  name: 'Grace Church',
  admin_name: 'Olive Owner',
  admin_id: 'olive',
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
  admin_id: 'ada',
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
    expect(screen.queryByRole('link', { name: 'Organisations' })).toBeNull()
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

  it('moves focus into the question to close, and back to the button when it is dropped', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), owner({ [CHURCHES]: () => json(200, { items: [OWN, HOPE], total: 2 }) }))
    renderApp('/member/churches')
    await user.click(await screen.findByRole('button', { name: 'Close Hope Church' }))
    expect(screen.getByText(/It cannot be undone/)).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Close Hope Church' })).toHaveFocus()
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
          json(201, { id: 'i1', token: FIRST, expires_at: '2026-11-28T08:00:00Z' }),
      }),
    )
    renderApp('/member/churches')
    await fill(user, ' Hope Church ', 'ada@example.com')
    await user.click(screen.getByRole('button', { name: 'Create the invitation' }))
    expect(await screen.findByText(/shown only now/)).toBeVisible()
    expect(screen.getByLabelText('Invitation link')).toHaveValue(
      `${window.location.origin}/invite/${FIRST}`,
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
            ? json(201, { id: 'i1', token: FIRST, expires_at: '2026-11-28T08:00:00Z' })
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
      `${window.location.origin}/invite/${FIRST}`,
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

describe('replace the ADMIN of a church', () => {
  const MEMBERS = 'GET /verifier/members?limit=50&offset=0&church_id=church-2'
  const member = (id: string, name: string, status: string) => ({
    id,
    full_name: name,
    status,
    home_group: { id: 'g2', name: 'Harbour' },
    status_set_by: null,
    flagged_for_recheck: false,
  })
  const withChurches = (extra = {}) =>
    owner({ [CHURCHES]: () => json(200, { items: [OWN, HOPE, OLD], total: 3 }), ...extra })
  const open = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.click(
      await screen.findByRole('button', { name: 'Replace the admin of Hope Church' }),
    )
  }

  it('is offered for another open church only', async () => {
    signedInAs(makeMe(), withChurches())
    renderApp('/member/churches')
    await screen.findByRole('heading', { name: 'Hope Church' })
    expect(screen.getAllByRole('button', { name: /^Replace the admin of/ })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: 'Replace the admin of Grace Church' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Replace the admin of Old Church' })).toBeNull()
  })

  it('chooses a member who is not the old ADMIN, what the old one becomes, and who leads their group', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () =>
          json(200, {
            items: [
              member('ada', 'Ada Admin', 'admin'),
              member('m1', 'Mia Member', 'provider'),
              member('m2', 'Max Member', 'searcher'),
            ],
            total: 3,
          }),
        'PUT /churches/church-2/admin': () =>
          json(200, {
            church: { id: 'church-2', name: 'Hope Church' },
            admin: { id: 'm1', name: 'Mia Member' },
            former_admin_keeps_leading: false,
          }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    // Offered for the new ADMIN and for the leader of the old ADMIN's group.
    expect(await screen.findAllByRole('option', { name: /Mia Member/ })).toHaveLength(2)
    expect(screen.queryByRole('option', { name: /Ada Admin/ })).toBeNull()
    const submit = screen.getByRole('button', { name: 'Replace the admin' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('New admin'), 'm1')
    await user.selectOptions(screen.getByLabelText('The old admin becomes'), 'searcher')
    await user.selectOptions(screen.getByLabelText(/^Leads the .* the old admin led/), 'm2')
    await user.click(submit)
    expect(await screen.findByText(/Mia Member is the admin of Hope Church now/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /churches/church-2/admin')?.body).toEqual({
      successor_id: 'm1',
      former_admin_status: 'searcher',
      group_successor_id: 'm2',
    })
  })

  it('sends no group successor when none is chosen, and says if the old ADMIN keeps their group', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () =>
          json(200, {
            items: [member('ada', 'Ada Admin', 'admin'), member('m1', 'Mia Member', 'provider')],
            total: 2,
          }),
        'PUT /churches/church-2/admin': () =>
          json(200, {
            church: { id: 'church-2', name: 'Hope Church' },
            admin: { id: 'm1', name: 'Mia Member' },
            former_admin_keeps_leading: true,
          }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await user.selectOptions(await screen.findByLabelText('New admin'), 'm1')
    await user.click(screen.getByRole('button', { name: 'Replace the admin' }))
    expect(await screen.findByText(/Ada Admin keeps leading their home group/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /churches/church-2/admin')?.body).toEqual({
      successor_id: 'm1',
      former_admin_status: 'provider',
    })
  })

  it('says when nobody else is in the church, and can be closed', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () => json(200, { items: [member('ada', 'Ada Admin', 'admin')], total: 1 }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    expect(await screen.findByText(/There is nobody else in this/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Replace the admin of Hope Church' })).toBeVisible()
  })

  it.each([
    ['successor_not_member', 409, /Choose a member of this/],
    ['invalid_choice', 422, /does not fit/],
    ['status_not_allowed', 403, /may not make this change/],
    ['state_changed', 409, /changed meanwhile/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () => json(200, { items: [member('m1', 'Mia Member', 'provider')], total: 1 }),
        'PUT /churches/church-2/admin': () => apiError(status, code),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await user.selectOptions(await screen.findByLabelText('New admin'), 'm1')
    await user.click(screen.getByRole('button', { name: 'Replace the admin' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('notes a cut-off list and retries a failed load', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [member('m1', 'Mia Member', 'provider')], total: 90 }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Only the first 1 of 90 members are shown.')).toBeVisible()
  })

  it("offers as leader of the old ADMIN's group only the members of that group", async () => {
    const user = userEvent.setup({ delay: null })
    const inOther = {
      ...member('m3', 'Zed Elsewhere', 'provider'),
      home_group: { id: 'g9', name: 'North' },
    }
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () =>
          json(200, {
            items: [
              member('ada', 'Ada Admin', 'admin'),
              member('m1', 'Mia Member', 'provider'),
              inOther,
            ],
            total: 3,
          }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await screen.findAllByRole('option', { name: /Zed Elsewhere/ })
    const groupSelect = screen.getByLabelText(/^Leads the .* the old admin led/)
    const names = Array.from(groupSelect.querySelectorAll('option')).map((o) => o.textContent)
    expect(names.some((n) => n?.includes('Mia Member'))).toBe(true)
    expect(names.some((n) => n?.includes('Zed Elsewhere'))).toBe(false)
    // The new ADMIN may be chosen from anyone in the church.
    const successor = screen.getByLabelText('New admin')
    expect(
      Array.from(successor.querySelectorAll('option')).some((o) => o.textContent?.includes('Zed')),
    ).toBe(true)
  })

  it('offers nobody as leader of their group when the old ADMIN is not in the loaded page', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () => json(200, { items: [member('m1', 'Mia Member', 'provider')], total: 90 }),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await screen.findAllByRole('option', { name: /Mia Member/ })
    const groupSelect = screen.getByLabelText(/^Leads the .* the old admin led/)
    expect(groupSelect.querySelectorAll('option')).toHaveLength(1)
    expect(screen.getByLabelText('New admin').querySelectorAll('option')).toHaveLength(2)
  })

  it('forgets a refusal and the choices when the form is dropped and opened again', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withChurches({
        [MEMBERS]: () => json(200, { items: [member('m1', 'Mia Member', 'provider')], total: 1 }),
        'PUT /churches/church-2/admin': () => apiError(409, 'state_changed'),
      }),
    )
    renderApp('/member/churches')
    await open(user)
    await user.selectOptions(await screen.findByLabelText('New admin'), 'm1')
    await user.selectOptions(screen.getByLabelText('The old admin becomes'), 'searcher')
    await user.click(screen.getByRole('button', { name: 'Replace the admin' }))
    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await open(user)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(await screen.findByLabelText('New admin')).toHaveValue('')
    expect(screen.getByLabelText('The old admin becomes')).toHaveValue('provider')
  })

  it('shows a loading line while the members come, and hides the close button meanwhile', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), withChurches({ [MEMBERS]: () => new Promise(() => {}) as never }))
    renderApp('/member/churches')
    await open(user)
    expect(await screen.findByRole('status')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Close Hope Church' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Close Hope Church' })).toBeVisible()
  })
})
