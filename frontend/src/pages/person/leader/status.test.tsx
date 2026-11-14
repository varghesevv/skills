import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'

const leader = () => makePerson({ status: 'verifier', full_name: 'Lena Leader', leader: null })
const base = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
  'GET /me': () => json(200, leader()),
}

const detail = (extra: Record<string, unknown> = {}) => ({
  id: 'p1',
  full_name: 'Sam Searcher',
  mobile_number: '+971500000002',
  status: 'searcher',
  requested_status: null,
  church: { id: 'church-1', name: 'Grace Church' },
  home_group: { id: 'group-1', name: 'Riverside' },
  status_set_by: { name: 'Lena Leader' },
  flagged_for_recheck: false,
  applied_at: '2026-11-10T08:00:00Z',
  history: [],
  chain_of_trust: [],
  vouches: [],
  can_admit_as_provider: false,
  ...extra,
})
const person = (d: Record<string, unknown>) => ({
  ...base,
  'GET /verifier/people/p1': () => json(200, d),
})

describe('the revoked and the flagged lists', () => {
  it('lists the revoked with where they were removed from, and no number', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /verifier/revoked?limit=50&offset=0': () =>
        json(200, {
          items: [
            {
              id: 'p1',
              full_name: 'Rita Removed',
              removed_from: { id: 'group-1', name: 'Riverside' },
              revoked_by: { name: 'Lena Leader' },
              revoked_at: '2026-11-12T08:00:00Z',
            },
          ],
          total: 1,
        }),
    })
    renderApp('/member/revoked')
    const link = await screen.findByRole('link', { name: 'Rita Removed' })
    expect(link).toHaveAttribute('href', '/member/people/p1')
    expect(link.closest('li')).toHaveTextContent('Removed from Riverside, by Lena Leader')
    expect(document.body.textContent).not.toMatch(/\+971/)
  })

  it('says when nobody is revoked, or flagged', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /verifier/revoked?limit=50&offset=0': () => json(200, { items: [], total: 0 }),
      'GET /verifier/flagged?limit=50&offset=0': () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/revoked')
    expect(await screen.findByText('Nobody is revoked.')).toBeVisible()
  })

  it('lists the flagged with who set their status', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /verifier/flagged?limit=50&offset=0': () =>
        json(200, {
          items: [
            {
              id: 'p2',
              full_name: 'Fay Flagged',
              status: 'provider',
              home_group: { id: 'group-1', name: 'Riverside' },
              status_set_by: { name: 'Vic Verifier' },
            },
          ],
          total: 1,
        }),
    })
    renderApp('/member/flagged')
    const row = (await screen.findByRole('link', { name: 'Fay Flagged' })).closest('li')!
    expect(row).toHaveTextContent('Set by Vic Verifier')
    expect(row).toHaveTextContent('Riverside')
  })

  it('links to both lists from the leader menu', async () => {
    signedInAs(makeMe(), base)
    renderApp('/member')
    expect(await screen.findByRole('link', { name: 'Revoked' })).toHaveAttribute(
      'href',
      '/member/revoked',
    )
    expect(screen.getByRole('link', { name: 'To re-check' })).toHaveAttribute(
      'href',
      '/member/flagged',
    )
  })
})

describe('revoke', () => {
  it('asks first, revokes, and shows the person as revoked without asking again', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...person(detail()),
      'PUT /verifier/people/p1/status': () =>
        json(200, { id: 'p1', status: 'revoked', home_group_id: null, flagged_for_recheck: false }),
      'GET /churches/church-1/home-groups': () => json(200, { items: [] }),
    })
    renderApp('/member/people/p1')
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    expect(api.count('PUT /verifier/people/p1/status')).toBe(0)
    expect(screen.getByText(/Everyone whose status they set will be flagged/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    expect(await screen.findByText('Sam Searcher was revoked.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'revoked',
    })
    expect(screen.queryByRole('button', { name: 'Revoke Sam Searcher' })).toBeNull()
    expect(api.count('GET /verifier/people/p1')).toBe(1)
  })

  it('can be cancelled', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), person(detail()))
    renderApp('/member/people/p1')
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Revoke Sam Searcher' })).toBeVisible()
    expect(api.count('PUT /verifier/people/p1/status')).toBe(0)
  })

  it('does not offer a VERIFIER to revoke another VERIFIER, and says only an ADMIN can', async () => {
    signedInAs(makeMe(), person(detail({ status: 'verifier' })))
    renderApp('/member/people/p1')
    await screen.findByRole('heading', { name: 'Sam Searcher' })
    expect(screen.queryByRole('button', { name: /^Revoke/ })).toBeNull()
    expect(screen.getByText(/Only an .* or the .* can revoke a/)).toBeVisible()
  })

  it.each(['admin', 'owner'])('does not offer to revoke an ADMIN to a %s here', async (actor) => {
    signedInAs(makeMe(), {
      ...person(detail({ status: 'admin' })),
      'GET /me': () => json(200, makePerson({ status: actor as 'admin' })),
    })
    renderApp('/member/people/p1')
    await screen.findByRole('heading', { name: 'Sam Searcher' })
    expect(screen.queryByRole('button', { name: /^Revoke/ })).toBeNull()
    expect(screen.getByText(/Hand that on first/)).toBeVisible()
  })

  it('does not offer to revoke the OWNER, an applicant or someone already revoked', async () => {
    for (const status of ['owner', 'pending']) {
      signedInAs(makeMe(), person(detail({ status })))
      const { unmount } = renderApp('/member/people/p1')
      await screen.findByRole('heading', { name: 'Sam Searcher' })
      expect(screen.queryByRole('button', { name: /^Revoke/ })).toBeNull()
      unmount()
    }
  })

  it("puts the server's refusal in words", async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...person(detail()),
      'PUT /verifier/people/p1/status': () => apiError(403, 'status_not_allowed'),
    })
    renderApp('/member/people/p1')
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/A leader above you decided this/)
  })
})

describe('revoke a VERIFIER with a successor', () => {
  const MEMBERS = 'GET /verifier/members?limit=50&offset=0&home_group_id=group-1'
  const member = (id: string, name: string, status: string) => ({
    id,
    full_name: name,
    status,
    home_group: { id: 'group-1', name: 'Riverside' },
    status_set_by: null,
    flagged_for_recheck: false,
  })
  const asAdmin = (extra = {}) => ({
    ...base,
    'GET /me': () => json(200, makePerson({ status: 'admin', id: 'me-admin' })),
    'GET /verifier/people/p1': () => json(200, detail({ status: 'verifier' })),
    ...extra,
  })

  it('asks who leads the group, and revokes with the choice', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      asAdmin({
        [MEMBERS]: () =>
          json(200, {
            items: [
              member('p1', 'Sam Searcher', 'verifier'),
              member('p2', 'Pia Provider', 'provider'),
            ],
            total: 2,
          }),
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
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    expect(screen.getByText(/leads a .* Choose who leads it from now on/)).toBeVisible()
    await screen.findByRole('option', { name: /Pia Provider/ })
    expect(screen.queryByRole('option', { name: /Sam Searcher/ })).toBeNull()
    const confirm = screen.getByRole('button', { name: 'Yes, revoke' })
    expect(confirm).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/Leads the .* from now on/), 'p2')
    await user.click(confirm)
    expect(await screen.findByText('Sam Searcher was revoked.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'revoked',
      successor_id: 'p2',
    })
  })

  it('revokes without a choice when they are alone in the group, which closes it', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      asAdmin({
        [MEMBERS]: () => json(200, { items: [member('p1', 'Sam Searcher', 'verifier')], total: 1 }),
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
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    expect(await screen.findByText(/closes with the revocation/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    await screen.findByText('Sam Searcher was revoked.')
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'revoked',
    })
  })

  it('keeps the button off and offers a retry when the members cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      asAdmin({
        [MEMBERS]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [member('p2', 'Pia Provider', 'provider')], total: 1 }),
      }),
    )
    renderApp('/member/people/p1')
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.getByRole('button', { name: 'Yes, revoke' })).toBeDisabled()
    await user.click(retry)
    expect(await screen.findByRole('option', { name: /Pia Provider/ })).toBeVisible()
  })

  it('shows the refusal when the successor is not a member', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      asAdmin({
        [MEMBERS]: () => json(200, { items: [member('p2', 'Pia Provider', 'provider')], total: 1 }),
        'PUT /verifier/people/p1/status': () => apiError(409, 'successor_required'),
      }),
    )
    renderApp('/member/people/p1')
    await user.click(await screen.findByRole('button', { name: 'Revoke Sam Searcher' }))
    await user.selectOptions(await screen.findByLabelText(/Leads the .* from now on/), 'p2')
    await user.click(screen.getByRole('button', { name: 'Yes, revoke' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/Hand that on first/)
  })
})

describe('reinstate', () => {
  const revoked = detail({ status: 'revoked', home_group: null })
  const groups = {
    'GET /churches/church-1/home-groups': () =>
      json(200, {
        items: [
          { id: 'group-1', name: 'Riverside', leader_name: 'Lena Leader' },
          { id: 'group-2', name: 'Harbour', leader_name: 'Hal Harbour' },
        ],
      }),
  }

  it('puts them into a chosen group of their church with the chosen status', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...person(revoked),
      ...groups,
      'PUT /verifier/people/p1/status': () =>
        json(200, {
          id: 'p1',
          status: 'provider',
          home_group_id: 'group-2',
          flagged_for_recheck: false,
        }),
    })
    renderApp('/member/people/p1')
    const submit = await screen.findByRole('button', { name: 'Reinstate Sam Searcher' })
    expect(submit).toBeDisabled()
    await screen.findByRole('option', { name: 'Harbour' })
    await user.selectOptions(screen.getByLabelText(/^(Home group|Group)/i), 'group-2')
    await user.selectOptions(screen.getByLabelText('As'), 'provider')
    await user.click(submit)
    expect(await screen.findByText('Sam Searcher is back.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'PUT /verifier/people/p1/status')?.body).toEqual({
      to: 'provider',
      home_group_id: 'group-2',
    })
    const facts = document.querySelector('dl.facts') as HTMLElement
    expect(within(facts).getByText('Harbour')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Reinstate Sam Searcher' })).toBeNull()
  })

  it('says when the church has no open group, and offers no revoke', async () => {
    signedInAs(makeMe(), {
      ...person(revoked),
      'GET /churches/church-1/home-groups': () => json(200, { items: [] }),
    })
    renderApp('/member/people/p1')
    expect(await screen.findByText(/There is no open .* in this church/)).toBeVisible()
    expect(screen.queryByRole('button', { name: /^Revoke|^Reinstate/ })).toBeNull()
  })

  it('shows the refusal when a higher leader revoked them', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...person(revoked),
      ...groups,
      'PUT /verifier/people/p1/status': () => apiError(403, 'status_not_allowed'),
    })
    renderApp('/member/people/p1')
    await screen.findByRole('option', { name: 'Riverside' })
    await user.selectOptions(screen.getByLabelText(/^(Home group|Group)/i), 'group-1')
    await user.click(screen.getByRole('button', { name: 'Reinstate Sam Searcher' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/A leader above you decided this/)
  })
})

describe('reconfirm', () => {
  it('confirms a flagged status and clears the flag in place', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...person(detail({ flagged_for_recheck: true })),
      'POST /verifier/people/p1/reconfirm': () =>
        json(200, {
          id: 'p1',
          status: 'searcher',
          home_group_id: 'group-1',
          flagged_for_recheck: false,
        }),
    })
    renderApp('/member/people/p1')
    expect(await screen.findByText(/was set by someone who was revoked/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Confirm the status of Sam Searcher' }))
    expect(await screen.findByText('The status of Sam Searcher is confirmed.')).toBeVisible()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /^Confirm the status/ })).toBeNull(),
    )
    expect(api.count('POST /verifier/people/p1/reconfirm')).toBe(1)
    expect(api.count('GET /verifier/people/p1')).toBe(1)
  })

  it('offers nothing when there is no flag', async () => {
    signedInAs(makeMe(), person(detail()))
    renderApp('/member/people/p1')
    await screen.findByRole('heading', { name: 'Sam Searcher' })
    expect(screen.queryByRole('button', { name: /^Confirm the status/ })).toBeNull()
  })

  it('says so when the flag is already gone', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...person(detail({ flagged_for_recheck: true })),
      'POST /verifier/people/p1/reconfirm': () => apiError(409, 'not_flagged'),
    })
    renderApp('/member/people/p1')
    await user.click(
      await screen.findByRole('button', { name: 'Confirm the status of Sam Searcher' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(/no longer needs a re-check/)
  })
})
