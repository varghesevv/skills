import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'

const NOTES = 'GET /me/notifications?limit=50'
const APPLICANTS = 'GET /verifier/applicants?limit=50&offset=0'
const MEMBERS = 'GET /verifier/members?limit=50&offset=0'

const leader = () => makePerson({ status: 'verifier', full_name: 'Lena Leader', leader: null })
const base = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }

const NADIA = {
  id: 'p1',
  full_name: 'Nadia Applicant',
  requested_status: 'provider',
  home_group: { id: 'group-1', name: 'Riverside' },
  applied_at: '2026-11-10T08:00:00Z',
  vouch_count: 2,
  vouchers: [
    { name: 'Vera Voucher', church_name: 'Hope Church', live: true },
    { name: 'Pia Provider', church_name: 'Grace Church', live: true },
    { name: 'Old Voucher', church_name: 'Grace Church', live: false },
  ],
}
const QUIET = {
  id: 'p2',
  full_name: 'Quinn Quiet',
  requested_status: 'searcher',
  home_group: { id: 'group-1', name: 'Riverside' },
  applied_at: '2026-11-11T08:00:00Z',
  vouch_count: 0,
  vouchers: [],
}

describe('who sees the screens of a leader', () => {
  it.each(['verifier', 'admin', 'owner'] as const)('shows the links to a %s', async (status) => {
    signedInAs(makeMe(), { ...base, 'GET /me': () => json(200, makePerson({ status })) })
    renderApp('/member')
    expect(await screen.findByRole('link', { name: 'Applicants' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Members' })).toBeVisible()
  })

  it.each(['pending', 'searcher', 'provider'] as const)(
    'shows nothing of it to a %s, and sends them home from the addresses',
    async (status) => {
      const api = signedInAs(makeMe(), {
        ...base,
        'GET /me': () => json(200, makePerson({ status })),
      })
      renderApp('/member/applicants')
      await waitFor(() => expect(screen.queryByRole('heading', { name: 'Applicants' })).toBeNull())
      expect(screen.queryByRole('link', { name: 'Applicants' })).toBeNull()
      expect(api.count(APPLICANTS)).toBe(0)
    },
  )
})

describe('applicants', () => {
  const routes = (extra = {}) => ({
    ...base,
    'GET /me': () => json(200, leader()),
    [APPLICANTS]: () => json(200, { items: [NADIA, QUIET], total: 2 }),
    ...extra,
  })

  it('lists them with what they apply for and every voucher, and no number', async () => {
    signedInAs(makeMe(), routes())
    renderApp('/member/applicants')
    const nadia = (await screen.findByRole('heading', { name: 'Nadia Applicant' })).closest('li')!
    expect(within(nadia).getByText(/Applying to offer their skills as a freelancer/)).toBeVisible()
    expect(within(nadia).getByText('2 vouches')).toBeVisible()
    expect(within(nadia).getByText(/Vera Voucher, Hope Church/)).toBeVisible()
    expect(within(nadia).getByText(/Old Voucher, Grace Church/)).toBeVisible()
    expect(within(nadia).getByText(/does not count now/)).toBeVisible()
    const quinn = screen.getByRole('heading', { name: 'Quinn Quiet' }).closest('li')!
    expect(within(quinn).getByText(/No vouches yet/)).toBeVisible()
    expect(document.body.textContent).not.toMatch(/\+971/)
    expect(within(nadia).getByRole('link', { name: 'Details of Nadia Applicant' })).toHaveAttribute(
      'href',
      '/member/people/p1',
    )
  })

  it('admits as a searcher and reloads the list', async () => {
    const user = userEvent.setup({ delay: null })
    let admitted = false
    const api = signedInAs(
      makeMe(),
      routes({
        [APPLICANTS]: () => json(200, { items: admitted ? [QUIET] : [NADIA, QUIET], total: 2 }),
        'POST /verifier/people/p1/admit': () => {
          admitted = true
          return json(200, { id: 'p1', status: 'searcher', requested_status: null })
        },
      }),
    )
    renderApp('/member/applicants')
    await user.click(
      await screen.findByRole('button', { name: 'Admit Nadia Applicant as a work host' }),
    )
    expect(await screen.findByText('Nadia Applicant was admitted.')).toBeVisible()
    expect(api.last('POST /verifier/people/p1/admit')?.body).toEqual({ to: 'searcher' })
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Nadia Applicant' })).toBeNull(),
    )
  })

  it('admits as a provider when there is a vouch, and not without one', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      routes({
        'POST /verifier/people/p1/admit': () =>
          json(200, { id: 'p1', status: 'provider', requested_status: null }),
      }),
    )
    renderApp('/member/applicants')
    const quinn = (await screen.findByRole('heading', { name: 'Quinn Quiet' })).closest('li')!
    expect(
      within(quinn).getByRole('button', { name: 'Admit Quinn Quiet as a freelancer' }),
    ).toBeDisabled()
    expect(within(quinn).getByText(/needs a vouch from someone besides you/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Admit Nadia Applicant as a freelancer' }))
    expect(await screen.findByText('Nadia Applicant was admitted.')).toBeVisible()
    expect(api.last('POST /verifier/people/p1/admit')?.body).toEqual({ to: 'provider' })
  })

  it.each([
    [409, 'not_enough_vouches', /needs a vouch from someone besides you/],
    [409, 'not_pending', /no longer waiting/],
    [409, 'state_changed', /changed meanwhile/],
    [404, 'not_found', /no longer exists/],
  ])('explains a refused admission (%s %s)', async (status, code, text) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), routes({ 'POST /verifier/people/p1/admit': () => apiError(status, code) }))
    renderApp('/member/applicants')
    await user.click(
      await screen.findByRole('button', { name: 'Admit Nadia Applicant as a work host' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })

  it('asks before declining, and does nothing when cancelled', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      routes({ 'POST /verifier/people/p1/decline': () => json(204) }),
    )
    renderApp('/member/applicants')
    const nadia = (await screen.findByRole('heading', { name: 'Nadia Applicant' })).closest('li')!
    await user.click(within(nadia).getByRole('button', { name: 'Decline Nadia Applicant' }))
    expect(within(nadia).getByText(/Nobody is revoked, and they can sign up again/)).toBeVisible()
    await user.click(within(nadia).getByRole('button', { name: 'Cancel' }))
    expect(api.count('POST /verifier/people/p1/decline')).toBe(0)
    await user.click(within(nadia).getByRole('button', { name: 'Decline Nadia Applicant' }))
    await user.click(within(nadia).getByRole('button', { name: 'Yes, decline' }))
    expect(
      await screen.findByText('The application of Nadia Applicant was declined.'),
    ).toBeVisible()
    expect(api.count('POST /verifier/people/p1/decline')).toBe(1)
  })

  it('says when nobody waits, and offers a retry when the list cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(
      makeMe(),
      routes({
        [APPLICANTS]: () =>
          ++attempts === 1
            ? apiError(503, 'service_unavailable')
            : json(200, { items: [], total: 0 }),
      }),
    )
    renderApp('/member/applicants')
    expect(await screen.findByRole('alert')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Nobody is waiting to be admitted.')).toBeVisible()
  })

  it('asks for the next page by offset', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      routes({
        [APPLICANTS]: () => json(200, { items: [NADIA], total: 120 }),
        'GET /verifier/applicants?limit=50&offset=50': () =>
          json(200, { items: [QUIET], total: 120 }),
      }),
    )
    renderApp('/member/applicants')
    await screen.findByRole('heading', { name: 'Nadia Applicant' })
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('heading', { name: 'Quinn Quiet' })).toBeVisible()
    expect(api.count('GET /verifier/applicants?limit=50&offset=50')).toBe(1)
  })
})

describe('members', () => {
  const MEMBER_LIST = {
    items: [
      {
        id: 'm1',
        full_name: 'Pia Provider',
        status: 'provider',
        home_group: { id: 'group-1', name: 'Riverside' },
        status_set_by: { name: 'Lena Leader' },
        flagged_for_recheck: true,
      },
      {
        id: 'm2',
        full_name: 'Sam Searcher',
        status: 'searcher',
        home_group: { id: 'group-1', name: 'Riverside' },
        status_set_by: null,
        flagged_for_recheck: false,
      },
    ],
    total: 2,
  }

  it('lists them with status and group, marks the flagged, and shows no number', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, leader()),
      [MEMBERS]: () => json(200, MEMBER_LIST),
    })
    renderApp('/member/members')
    const pia = (await screen.findByRole('link', { name: 'Pia Provider' })).closest('li')!
    expect(pia).toHaveTextContent('Freelancer')
    expect(pia).toHaveTextContent('Riverside')
    expect(pia).toHaveTextContent('Admitted by Lena Leader')
    expect(within(pia).getByText('To be re-checked')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Pia Provider' })).toHaveAttribute(
      'href',
      '/member/people/m1',
    )
    expect(document.body.textContent).not.toMatch(/\+971/)
  })

  it('filters by status and starts again from the first page', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, leader()),
      [MEMBERS]: () => json(200, MEMBER_LIST),
      'GET /verifier/members?limit=50&offset=0&status=provider': () =>
        json(200, { items: [MEMBER_LIST.items[0]], total: 1 }),
    })
    renderApp('/member/members')
    await screen.findByRole('link', { name: 'Sam Searcher' })
    await user.selectOptions(screen.getByLabelText('Show'), 'provider')
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Sam Searcher' })).toBeNull())
    expect(api.count('GET /verifier/members?limit=50&offset=0&status=provider')).toBe(1)
  })

  it('goes back to the first page when the filter changes', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, leader()),
      [MEMBERS]: () => json(200, { items: [MEMBER_LIST.items[0]], total: 120 }),
      'GET /verifier/members?limit=50&offset=50': () =>
        json(200, { items: [MEMBER_LIST.items[1]], total: 120 }),
      'GET /verifier/members?limit=50&offset=0&status=provider': () =>
        json(200, { items: [MEMBER_LIST.items[0]], total: 1 }),
    })
    renderApp('/member/members')
    await screen.findByRole('link', { name: 'Pia Provider' })
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByRole('link', { name: 'Sam Searcher' })
    await user.selectOptions(screen.getByLabelText('Show'), 'provider')
    expect(await screen.findByRole('link', { name: 'Pia Provider' })).toBeVisible()
    expect(api.count('GET /verifier/members?limit=50&offset=0&status=provider')).toBe(1)
    expect(api.calls.some((c) => c.key.includes('offset=50&status='))).toBe(false)
  })

  it('says when nobody is admitted yet', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, leader()),
      [MEMBERS]: () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/members')
    expect(await screen.findByText('Nobody has been admitted yet.')).toBeVisible()
  })
})

describe('one person', () => {
  const DETAIL: Record<string, unknown> = {
    id: 'p1',
    full_name: 'Nadia Applicant',
    mobile_number: '+971500000002',
    status: 'pending',
    requested_status: 'provider',
    church: { id: 'church-1', name: 'Grace Church' },
    home_group: { id: 'group-1', name: 'Riverside' },
    status_set_by: null,
    flagged_for_recheck: false,
    applied_at: '2026-11-10T08:00:00Z',
    history: [
      {
        kind: 'signup',
        from_status: null,
        to_status: 'pending',
        changed_by: null,
        at: '2026-11-10T08:00:00Z',
      },
    ],
    chain_of_trust: [{ id: 'c1', full_name: 'Olga Owner', status: 'owner' }],
    vouches: [{ name: 'Vera Voucher', church_name: 'Hope Church', live: true }],
  }
  const routes = (detail = DETAIL, extra = {}) => ({
    ...base,
    'GET /me': () => json(200, leader()),
    'GET /verifier/people/p1': () => json(200, detail),
    ...extra,
  })

  it('shows the number, the history and the chain, and asks the server once', async () => {
    const api = signedInAs(makeMe(), routes())
    renderApp('/member/people/p1')
    expect(await screen.findByRole('heading', { name: 'Nadia Applicant' })).toBeVisible()
    expect(screen.getByRole('link', { name: '+971500000002' })).toHaveAttribute(
      'href',
      'tel:+971500000002',
    )
    expect(screen.getByText(/Each time it is shown is recorded/)).toBeVisible()
    expect(screen.getByText(/Signed up: — to Waiting to be admitted, by the system/)).toBeVisible()
    expect(screen.getByText(/Olga Owner/)).toBeVisible()
    expect(screen.getByText(/Vera Voucher, Hope Church/)).toBeVisible()
    expect(api.count('GET /verifier/people/p1')).toBe(1)
  })

  it('offers admit and decline for an applicant, and nothing of the kind for a member', async () => {
    signedInAs(makeMe(), routes())
    renderApp('/member/people/p1')
    expect(
      await screen.findByRole('button', { name: 'Admit Nadia Applicant as a freelancer' }),
    ).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Decline Nadia Applicant' })).toBeVisible()
  })

  it('shows a member without the buttons', async () => {
    signedInAs(makeMe(), routes({ ...DETAIL, status: 'provider', requested_status: null }))
    renderApp('/member/people/p1')
    await screen.findByRole('heading', { name: 'Nadia Applicant' })
    expect(screen.queryByRole('button', { name: /^Admit/ })).toBeNull()
  })

  it('says so for someone out of scope or unknown, in the same words', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, leader()),
      'GET /verifier/people/p1': () => apiError(404, 'not_found'),
    })
    renderApp('/member/people/p1')
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByRole('link', { name: /tel:/ })).toBeNull()
  })
})
