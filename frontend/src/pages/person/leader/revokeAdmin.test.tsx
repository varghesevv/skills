import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'

const CHURCH = 'GET /verifier/members?limit=50&offset=0&church_id=church-1'
const GROUP = 'GET /verifier/members?limit=50&offset=0&home_group_id=group-1'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }

const detail = (extra: Record<string, unknown> = {}) => ({
  id: 'p1',
  full_name: 'Ada Admin',
  mobile_number: '+971500000002',
  status: 'admin',
  requested_status: null,
  church: { id: 'church-1', name: 'Hope Church' },
  home_group: { id: 'group-1', name: 'Harbour' },
  status_set_by: { name: 'Olive Owner' },
  flagged_for_recheck: false,
  applied_at: '2026-11-10T08:00:00Z',
  history: [],
  chain_of_trust: [],
  vouches: [],
  can_admit_as_provider: false,
  ...extra,
})
const member = (id: string, name: string, status = 'provider') => ({
  id,
  full_name: name,
  status,
  home_group: { id: 'group-1', name: 'Harbour' },
  status_set_by: null,
  flagged_for_recheck: false,
})
const owner = (extra = {}) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ id: 'olive', status: 'owner' })),
  'GET /verifier/people/p1': () => json(200, detail()),
  [CHURCH]: () =>
    json(200, {
      items: [
        member('p1', 'Ada Admin', 'admin'),
        member('m1', 'Mia Member'),
        member('m2', 'Max Member', 'searcher'),
      ],
      total: 3,
    }),
  [GROUP]: () =>
    json(200, {
      items: [member('p1', 'Ada Admin', 'admin'), member('m2', 'Max Member', 'searcher')],
      total: 2,
    }),
  ...extra,
})
const open = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(await screen.findByRole('button', { name: 'Revoke Ada Admin' }))

describe('the OWNER revokes an ADMIN', () => {
  it('is offered to the OWNER and not to an ADMIN', async () => {
    signedInAs(makeMe(), owner())
    const { unmount } = renderApp('/member/people/p1')
    expect(await screen.findByRole('button', { name: 'Revoke Ada Admin' })).toBeVisible()
    unmount()
    signedInAs(makeMe(), {
      ...owner(),
      'GET /me': () => json(200, makePerson({ status: 'admin' })),
    })
    renderApp('/member/people/p1')
    await screen.findByRole('heading', { name: 'Ada Admin' })
    expect(screen.queryByRole('button', { name: 'Revoke Ada Admin' })).toBeNull()
  })

  it('needs a new ADMIN and the leader of the group, then sends both', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        'PUT /verifier/people/p1/status': () =>
          json(200, {
            id: 'p1',
            status: 'revoked',
            home_group_id: null,
            flagged_for_recheck: false,
          }),
      }),
    )
    renderApp('/member/people/p1')
    await open(user)
    expect(screen.getByText(/is the .* of Hope Church/)).toHaveFocus()
    await screen.findByRole('option', { name: /Mia Member/ })
    expect(screen.queryByRole('option', { name: /Ada Admin/ })).toBeNull()
    const confirm = screen.getByRole('button', { name: 'Yes, revoke' })
    expect(confirm).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/^New admin of Hope Church/i), 'm1')
    expect(confirm).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/^Leads the .* of Ada Admin/), 'm2')
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    expect(await screen.findByText('Ada Admin was revoked.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'revoked',
      successor_id: 'm1',
      group_successor_id: 'm2',
    })
  })

  it('sends no group successor when the ADMIN is alone in the group, which closes', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      owner({
        [GROUP]: () => json(200, { items: [member('p1', 'Ada Admin', 'admin')], total: 1 }),
        'PUT /verifier/people/p1/status': () =>
          json(200, {
            id: 'p1',
            status: 'revoked',
            home_group_id: null,
            flagged_for_recheck: false,
          }),
      }),
    )
    renderApp('/member/people/p1')
    await open(user)
    expect(await screen.findByText(/closes with the revocation/)).toBeVisible()
    await user.selectOptions(await screen.findByLabelText(/^New admin of Hope Church/i), 'm1')
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    await screen.findByText('Ada Admin was revoked.')
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'revoked',
      successor_id: 'm1',
    })
  })

  it('says to close the church when nobody else is in it, and keeps the button off', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      owner({
        [CHURCH]: () => json(200, { items: [member('p1', 'Ada Admin', 'admin')], total: 1 }),
        [GROUP]: () => json(200, { items: [member('p1', 'Ada Admin', 'admin')], total: 1 }),
      }),
    )
    renderApp('/member/people/p1')
    await open(user)
    expect(await screen.findByText(/Nobody else is in this .* Close the/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Yes, revoke' })).toBeDisabled()
  })

  it.each([
    ['successor_required', 409, /Choose a new .* and who leads/],
    ['successor_not_member', 409, /Choose members of this/],
    ['status_not_allowed', 403, /A leader above you decided this/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), owner({ 'PUT /verifier/people/p1/status': () => apiError(status, code) }))
    renderApp('/member/people/p1')
    await open(user)
    await user.selectOptions(await screen.findByLabelText(/^New admin of Hope Church/i), 'm1')
    await user.selectOptions(screen.getByLabelText(/^Leads the .* of Ada Admin/), 'm2')
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('retries a failed load, notes a cut-off list, and forgets the choices when dropped', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      owner({
        [CHURCH]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, {
                items: [member('p1', 'Ada Admin', 'admin'), member('m1', 'Mia Member')],
                total: 90,
              }),
      }),
    )
    renderApp('/member/people/p1')
    await open(user)
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Only the first 2 of 90 members are shown.')).toBeVisible()
    await user.selectOptions(screen.getByLabelText(/^New admin of Hope Church/i), 'm1')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Revoke Ada Admin' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Revoke Ada Admin' }))
    expect(await screen.findByLabelText(/^New admin of Hope Church/i)).toHaveValue('')
  })
})
