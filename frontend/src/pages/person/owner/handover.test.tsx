import { screen } from '@testing-library/react'
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

const CURRENT = 'GET /owner/handover'
const CHURCHES = 'GET /owner/churches?limit=50&offset=0'
const CHURCH_MEMBERS = 'GET /verifier/members?limit=50&offset=0&church_id=church-1'
const GROUP_MEMBERS = 'GET /verifier/members?limit=50&offset=0&home_group_id=group-1'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }

const OLIVE = { id: 'olive', name: 'Olive Owner' }
const ADA = { id: 'ada', name: 'Ada Admin' }
const row = (id: string, name: string, status: string) => ({
  id,
  full_name: name,
  status,
  home_group: { id: 'group-1', name: 'Riverside' },
  status_set_by: null,
  flagged_for_recheck: false,
})
const church = (
  id: string,
  name: string,
  adminId: string | null,
  adminName: string,
  open = true,
) => ({
  id,
  name,
  admin_name: adminName,
  admin_id: adminId,
  open,
  groups: 1,
  members: 3,
  revoked: 0,
  closed_at: open ? null : '2026-10-01T08:00:00Z',
})
const WAITING = {
  id: 'h1',
  owner: OLIVE,
  new_owner: ADA,
  successor_admin: { id: 'sam', name: 'Sam Successor' },
  successor_leader: null,
  former_owner_status: 'provider',
  created_at: '2026-11-12T08:00:00Z',
}

const owner = (extra = {}) => ({
  ...quiet,
  'GET /me': () =>
    json(
      200,
      makePerson({
        id: 'olive',
        status: 'owner',
        full_name: 'Olive Owner',
        leader: { name: 'Olive Owner' },
      }),
    ),
  [CURRENT]: () => json(200, { request: null }),
  [CHURCHES]: () =>
    json(200, {
      items: [
        church('church-1', 'Grace Church', 'olive', 'Olive Owner'),
        church('church-2', 'Hope Church', 'ada', 'Ada Admin'),
        church('church-3', 'Old Church', null, '', false),
      ],
      total: 3,
    }),
  [CHURCH_MEMBERS]: () =>
    json(200, {
      items: [row('olive', 'Olive Owner', 'owner'), row('sam', 'Sam Successor', 'provider')],
      total: 2,
    }),
  [GROUP_MEMBERS]: () =>
    json(200, {
      items: [row('olive', 'Olive Owner', 'owner'), row('lia', 'Lia Leader', 'searcher')],
      total: 2,
    }),
  ...extra,
})
const admin = (extra = {}) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ id: 'ada', status: 'admin', full_name: 'Ada Admin' })),
  [CURRENT]: () => json(200, { request: null }),
  ...extra,
})

describe('who sees the handover', () => {
  it.each(['owner', 'admin'])('shows the link and the page to an %s', async (status) => {
    signedInAs(makeMe(), status === 'owner' ? owner() : admin())
    renderApp('/member/handover')
    expect(await screen.findByRole('heading', { name: /Hand over the/ })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Handover' })).toHaveAttribute(
      'href',
      '/member/handover',
    )
  })

  it.each(['verifier', 'provider'])('sends a %s home', async (status) => {
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () => json(200, makePerson({ status: status as 'verifier' })),
      [CURRENT]: () => json(200, { request: null }),
    })
    renderApp('/member/handover')
    expect(await screen.findByText(/^Welcome/)).toBeVisible()
    expect(api.count(CURRENT)).toBe(0)
    expect(screen.queryByRole('link', { name: 'Handover' })).toBeNull()
  })

  it('sends a signed-out visitor to sign in', async () => {
    const api = mockApi({ [CURRENT]: () => json(200, { request: null }) })
    renderApp('/member/handover')
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeVisible()
    expect(api.count(CURRENT)).toBe(0)
  })

  it('tells an ADMIN with nothing waiting that nothing is', async () => {
    signedInAs(makeMe(), admin())
    renderApp('/member/handover')
    expect(await screen.findByText('No handover is waiting.')).toBeVisible()
  })
})

describe('the OWNER proposes', () => {
  const pick = async (user: ReturnType<typeof userEvent.setup>) => {
    await screen.findByRole('option', { name: /Ada Admin · Hope Church/ })
    await user.selectOptions(screen.getByLabelText(/^New owner$/i), 'ada')
  }

  it('offers only the ADMINs of other open churches, and members who are not the OWNER', async () => {
    signedInAs(makeMe(), owner())
    renderApp('/member/handover')
    await screen.findByRole('option', { name: /Ada Admin · Hope Church/ })
    expect(screen.queryByRole('option', { name: /Olive Owner/ })).toBeNull()
    expect(screen.queryByRole('option', { name: /Old Church/ })).toBeNull()
    expect(await screen.findByRole('option', { name: /Sam Successor/ })).toBeVisible()
    expect(await screen.findByRole('option', { name: /Lia Leader/ })).toBeVisible()
  })

  it('needs the new OWNER and both successors before it sends, then sends all four choices', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), owner({ 'POST /owner/handover': () => json(201, WAITING) }))
    renderApp('/member/handover')
    await pick(user)
    const submit = screen.getByRole('button', { name: 'Propose the handover' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/^New admin of your/i), 'sam')
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/^New leader of your/i), 'lia')
    await user.selectOptions(screen.getByLabelText('Afterwards I am'), 'searcher')
    expect(submit).toBeEnabled()
    await user.click(submit)
    expect(await screen.findByText(/Nothing changes until Ada Admin accepts/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /owner/handover')?.body).toEqual({
      new_owner_id: 'ada',
      successor_admin_id: 'sam',
      successor_leader_id: 'lia',
      former_owner_status: 'searcher',
    })
  })

  it('lets the OWNER who is alone keep the roles, sending no successors', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        [CHURCH_MEMBERS]: () =>
          json(200, { items: [row('olive', 'Olive Owner', 'owner')], total: 1 }),
        [GROUP_MEMBERS]: () =>
          json(200, { items: [row('olive', 'Olive Owner', 'owner')], total: 1 }),
        'POST /owner/handover': () => json(201, { ...WAITING, successor_admin: null }),
      }),
    )
    renderApp('/member/handover')
    await pick(user)
    expect(screen.getByText(/Nobody else is here/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Propose the handover' }))
    await screen.findByText(/Nothing changes until Ada Admin accepts/)
    expect(api.calls.find((c) => c.key === 'POST /owner/handover')?.body).toEqual({
      new_owner_id: 'ada',
      former_owner_status: 'provider',
    })
  })

  it('says when there is no other church to hand over to', async () => {
    signedInAs(
      makeMe(),
      owner({
        [CHURCHES]: () =>
          json(200, {
            items: [church('church-1', 'Grace Church', 'olive', 'Olive Owner')],
            total: 1,
          }),
      }),
    )
    renderApp('/member/handover')
    expect(
      await screen.findByText(/There is no other open .* with an .* to hand over to/),
    ).toBeVisible()
  })

  it.each([
    ['handover_open', 409, /proposed already/],
    ['invalid_choice', 422, /does not fit/],
    ['successor_required', 409, /Choose a new/],
    ['successor_not_member', 409, /must be a member of yours/],
    ['state_changed', 409, /changed meanwhile/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), owner({ 'POST /owner/handover': () => apiError(status, code) }))
    renderApp('/member/handover')
    await pick(user)
    await user.selectOptions(await screen.findByLabelText(/^New admin of your/i), 'sam')
    await user.selectOptions(screen.getByLabelText(/^New leader of your/i), 'lia')
    await user.click(screen.getByRole('button', { name: 'Propose the handover' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('tells the OWNER when only the first page of members is shown, and retries a failed load', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      owner({
        [CHURCH_MEMBERS]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [row('sam', 'Sam Successor', 'provider')], total: 90 }),
      }),
    )
    renderApp('/member/handover')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Only the first 1 of 90 members are shown.')).toBeVisible()
  })
})

describe('a handover that is waiting', () => {
  it('shows the OWNER what they proposed and cancels it', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        [CURRENT]: () => json(200, { request: WAITING }),
        'POST /owner/handover/h1/cancel': () => json(204),
      }),
    )
    renderApp('/member/handover')
    expect(await screen.findByText(/You proposed to hand the role to Ada Admin/)).toBeVisible()
    expect(screen.getByText(/Sam Successor/)).toBeVisible()
    expect(screen.queryByRole('button', { name: /^Accept/ })).toBeNull()
    expect(screen.queryByLabelText(/^New owner$/i)).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Cancel the handover' }))
    expect(await screen.findByText('The handover was cancelled.')).toBeVisible()
    expect(api.count('POST /owner/handover/h1/cancel')).toBe(1)
  })

  it('lets the chosen ADMIN accept after a question, and shows the outcome on their home as OWNER', async () => {
    const user = userEvent.setup({ delay: null })
    let accepted = false
    const api = signedInAs(makeMe(), {
      ...admin({
        'GET /me': () =>
          json(
            200,
            makePerson({ id: 'ada', status: accepted ? 'owner' : 'admin', full_name: 'Ada Admin' }),
          ),
        [CURRENT]: () => json(200, { request: accepted ? null : WAITING }),
        'POST /owner/handover/h1/accept': () => {
          accepted = true
          return json(200, { owner: ADA, former_owner: OLIVE, former_owner_status: 'provider' })
        },
      }),
    })
    renderApp('/member/handover')
    expect(await screen.findByText(/Olive Owner proposes to hand the .* role to you/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: /^Accept the/ }))
    expect(api.count('POST /owner/handover/h1/accept')).toBe(0)
    expect(screen.getByText(/This cannot be undone by you/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Yes, accept' }))
    expect(await screen.findByText(/You are the .* now. Olive Owner is provider/)).toBeVisible()
    expect(screen.getByText(/^Welcome/)).toBeVisible()
  })

  it('lets the chosen ADMIN decline, which cancels it', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      admin({
        [CURRENT]: () => json(200, { request: WAITING }),
        'POST /owner/handover/h1/cancel': () => json(204),
      }),
    )
    renderApp('/member/handover')
    await user.click(await screen.findByRole('button', { name: 'Decline the handover' }))
    expect(await screen.findByText('You declined the handover.')).toBeVisible()
    expect(api.count('POST /owner/handover/h1/cancel')).toBe(1)
  })

  it.each([
    ['not_open', 409, /decided already/],
    ['state_changed', 409, /changed meanwhile/],
  ])('puts %s of an acceptance in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      admin({
        [CURRENT]: () => json(200, { request: WAITING }),
        'POST /owner/handover/h1/accept': () => apiError(status, code),
      }),
    )
    renderApp('/member/handover')
    await user.click(await screen.findByRole('button', { name: /^Accept the/ }))
    await user.click(screen.getByRole('button', { name: 'Yes, accept' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('can be backed out of at the question', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), admin({ [CURRENT]: () => json(200, { request: WAITING }) }))
    renderApp('/member/handover')
    await user.click(await screen.findByRole('button', { name: /^Accept the/ }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: /^Accept the/ })).toBeVisible()
    expect(api.count('POST /owner/handover/h1/accept')).toBe(0)
  })

  it('shows an error with a retry when the handover cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      admin({
        [CURRENT]: () =>
          ++attempts === 1 ? apiError(503, 'service_unavailable') : json(200, { request: null }),
      }),
    )
    renderApp('/member/handover')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No handover is waiting.')).toBeVisible()
  })
})

describe('notifications about a handover', () => {
  it('reads each kind in words', async () => {
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'admin' })),
      [NOTES]: () =>
        json(200, {
          items: [
            'handover_requested',
            'handover_cancelled',
            'owner_handed_over',
            'owner_appointed',
          ].map((kind, i) => ({
            id: `n${i}`,
            kind,
            subject: { name: 'Olive Owner' },
            created_at: '2026-11-12T08:00:00Z',
            read: false,
          })),
          total: 4,
          unread_count: 4,
        }),
    })
    renderApp('/member/notifications')
    expect(await screen.findByText(/Olive Owner proposes to hand the/)).toBeVisible()
    expect(screen.getByText(/Olive Owner cancelled the handover/)).toBeVisible()
    expect(screen.getByText(/Olive Owner is the .* now; you handed/)).toBeVisible()
    expect(screen.getByText(/You are the .* now, after Olive Owner/)).toBeVisible()
    expect(screen.queryByText('Something happened')).toBeNull()
  })
})
