import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'

const GROUPS = 'GET /churches/church-1/home-groups'
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const as = (status: string) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ status: status as 'admin' })),
})
const row = (id: string, name: string, status: string, group = 'g1') => ({
  id,
  full_name: name,
  status,
  home_group: { id: group, name: 'Riverside' },
  status_set_by: null,
  flagged_for_recheck: false,
})
const TWO_GROUPS = () =>
  json(200, {
    items: [
      { id: 'g1', name: 'Riverside', leader_name: 'Lena Leader' },
      { id: 'g2', name: 'Harbour', leader_name: 'Hal Harbour' },
    ],
  })

describe('who sees the groups', () => {
  it.each(['admin', 'owner'])('shows the link and the page to an %s', async (status) => {
    signedInAs(makeMe(), { ...as(status), [GROUPS]: TWO_GROUPS })
    renderApp('/member/groups')
    expect(await screen.findByText('Leader: Lena Leader')).toBeVisible()
    expect(screen.getByText('Leader: Hal Harbour')).toBeVisible()
    expect(screen.getByRole('link', { name: /Home groups/i })).toHaveAttribute(
      'href',
      '/member/groups',
    )
  })

  it.each(['verifier', 'provider'])('sends a %s home, and shows no link', async (status) => {
    const api = signedInAs(makeMe(), { ...as(status), [GROUPS]: TWO_GROUPS })
    renderApp('/member/groups')
    // The home page appears: the redirect happened, so nothing of the groups was asked for.
    expect(await screen.findByText(/^Welcome/)).toBeVisible()
    expect(screen.queryByText('Leader: Lena Leader')).toBeNull()
    expect(screen.queryByRole('link', { name: /Home groups/i })).toBeNull()
    expect(api.count(GROUPS)).toBe(0)
  })
})

describe('change the leader of a group', () => {
  const MEMBERS = 'GET /verifier/members?limit=50&offset=0&home_group_id=g1'

  it('chooses a member (not the leader) and says what the old leader becomes', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...as('admin'),
      [GROUPS]: TWO_GROUPS,
      [MEMBERS]: () =>
        json(200, {
          items: [
            row('p1', 'Lena Leader', 'verifier'),
            row('p2', 'Sam Searcher', 'searcher'),
            row('p3', 'Pia Provider', 'provider'),
          ],
          total: 3,
        }),
      'PUT /home-groups/g1/leader': () =>
        json(200, {
          group: { id: 'g1', name: 'Riverside' },
          leader: { id: 'p3', name: 'Pia Provider' },
        }),
    })
    renderApp('/member/groups')
    await user.click(await screen.findByRole('button', { name: 'Change the leader of Riverside' }))
    await screen.findByRole('option', { name: /Pia Provider/ })
    expect(screen.queryByRole('option', { name: /Lena Leader/ })).toBeNull()
    const submit = screen.getByRole('button', { name: 'Change the leader' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('New leader'), 'p3')
    await user.selectOptions(screen.getByLabelText(/steps down becomes/), 'searcher')
    await user.click(submit)
    expect(await screen.findByText('Pia Provider leads Riverside from now on.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /home-groups/g1/leader')?.body).toEqual({
      successor_id: 'p3',
      former_leader_status: 'searcher',
    })
  })

  it('says so when nobody else is in the group', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...as('admin'),
      [GROUPS]: TWO_GROUPS,
      [MEMBERS]: () => json(200, { items: [row('p1', 'Lena Leader', 'verifier')], total: 1 }),
    })
    renderApp('/member/groups')
    await user.click(await screen.findByRole('button', { name: 'Change the leader of Riverside' }))
    expect(await screen.findByText(/Nobody else is in this .* yet/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Change the leader' })).toBeNull()
  })

  it.each([
    ['successor_not_member', 422, /Choose a member of this/],
    ['invalid_choice', 422, /does not fit this leader/],
    ['status_not_allowed', 403, /A leader above you decided this/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...as('admin'),
      [GROUPS]: TWO_GROUPS,
      [MEMBERS]: () => json(200, { items: [row('p2', 'Sam Searcher', 'searcher')], total: 1 }),
      'PUT /home-groups/g1/leader': () => apiError(status, code),
    })
    renderApp('/member/groups')
    await user.click(await screen.findByRole('button', { name: 'Change the leader of Riverside' }))
    await user.selectOptions(await screen.findByLabelText('New leader'), 'p2')
    await user.click(screen.getByRole('button', { name: 'Change the leader' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })
})

describe('move a member', () => {
  const DETAIL = {
    id: 'p2',
    full_name: 'Sam Searcher',
    mobile_number: '+971500000002',
    status: 'searcher',
    requested_status: null,
    church: { id: 'church-1', name: 'Grace Church' },
    home_group: { id: 'g1', name: 'Riverside' },
    status_set_by: null,
    flagged_for_recheck: false,
    applied_at: '2026-11-10T08:00:00Z',
    history: [],
    chain_of_trust: [],
    vouches: [],
    can_admit_as_provider: false,
  }
  const routes = (status: string, detail = DETAIL, extra = {}) => ({
    ...as(status),
    [GROUPS]: TWO_GROUPS,
    'GET /verifier/people/p2': () => json(200, detail),
    ...extra,
  })

  it('moves to another group of the church and shows the new group', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      routes('admin', DETAIL, {
        'POST /verifier/people/p2/move': () =>
          json(200, {
            person: { id: 'p2', name: 'Sam Searcher' },
            home_group: { id: 'g2', name: 'Harbour' },
          }),
      }),
    )
    renderApp('/member/people/p2')
    await screen.findByRole('option', { name: 'Harbour' })
    expect(screen.queryByRole('option', { name: 'Riverside' })).toBeNull()
    await user.selectOptions(screen.getByLabelText('Move to'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Move Sam Searcher' }))
    expect(await screen.findByText('Sam Searcher moved to Harbour.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /verifier/people/p2/move')?.body).toEqual({
      home_group_id: 'g2',
    })
    expect(document.querySelector('dl.facts')).toHaveTextContent('Harbour')
    expect(api.count('GET /verifier/people/p2')).toBe(1)
  })

  it('is not offered to a VERIFIER, nor for a leader, an applicant or a revoked person', async () => {
    for (const [actor, status] of [
      ['verifier', 'searcher'],
      ['admin', 'verifier'],
      ['admin', 'pending'],
      ['admin', 'revoked'],
    ]) {
      signedInAs(makeMe(), routes(actor, { ...DETAIL, status }))
      const { unmount } = renderApp('/member/people/p2')
      await screen.findByRole('heading', { name: 'Sam Searcher' })
      expect(screen.queryByRole('button', { name: /^Move Sam/ })).toBeNull()
      unmount()
    }
  })

  it('says why a leader cannot be moved', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      routes('admin', DETAIL, {
        'POST /verifier/people/p2/move': () => apiError(409, 'leads_a_group'),
      }),
    )
    renderApp('/member/people/p2')
    await screen.findByRole('option', { name: 'Harbour' })
    await user.selectOptions(screen.getByLabelText('Move to'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Move Sam Searcher' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Change the leader first/)
  })
})
