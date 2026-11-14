import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../testUtils'

const LIST = 'GET /group-requests?limit=50&offset=0'
const OWN_MEMBERS = 'GET /verifier/members?limit=50&offset=0&home_group_id=group-1'
const GROUP_MEMBERS = 'GET /verifier/members?limit=50&offset=0&home_group_id=g1'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }

const REQUEST = {
  id: 'r1',
  group_name: 'Harbour',
  church: { id: 'church-1', name: 'Grace Church' },
  requester: { id: 'p9', name: 'Pia Provider' },
  state: 'open',
  created_at: '2026-11-12T08:00:00Z',
  requester_leads_a_group: false,
  requester_group: { id: 'g1', name: 'Riverside' },
}

const as = (status: string, extra = {}) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ status: status as 'provider', ...extra })),
})

describe('a member asks for a home group', () => {
  it('sends the name, tells them it waits, and lists their own request', async () => {
    const user = userEvent.setup({ delay: null })
    let asked = false
    const api = signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () => json(200, { items: asked ? [REQUEST] : [], total: asked ? 1 : 0 }),
      'POST /group-requests': () => {
        asked = true
        return json(201, { request: REQUEST, group: null })
      },
    })
    renderApp('/member/group-requests')
    await screen.findByText('No requests.')
    await user.type(screen.getByLabelText(/^Name of the/), ' Harbour ')
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText(/Your request was sent/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /group-requests')?.body).toEqual({
      group_name: 'Harbour',
    })
    expect(await screen.findByText('Harbour')).toBeVisible()
    expect(screen.queryByRole('button', { name: /^Approve/ })).toBeNull()
  })

  it('keeps the button off for a name that is too short', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), { ...as('provider'), [LIST]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'H')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it.each([
    ['group_name_taken', /with this name already exists/],
    ['request_open', /already have a request waiting/],
  ])('puts %s in words', async (code, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () => json(200, { items: [], total: 0 }),
      'POST /group-requests': () => apiError(409, code),
    })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'Harbour')
    await user.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it.each(['pending', 'revoked'])('sends a %s person home', async (status) => {
    const api = signedInAs(makeMe(), as(status))
    renderApp('/member/group-requests')
    await waitFor(() => expect(screen.queryByLabelText(/^Name of the/)).toBeNull())
    expect(api.count(LIST)).toBe(0)
  })

  it('is linked from the home of an admitted member', async () => {
    signedInAs(makeMe(), as('provider'))
    renderApp('/member')
    expect(await screen.findByRole('link', { name: /^Start a/ })).toHaveAttribute(
      'href',
      '/member/group-requests',
    )
  })
})

describe('an ADMIN decides', () => {
  const admin = (extra = {}) => ({
    ...as('admin', extra),
    [LIST]: () => json(200, { items: [REQUEST], total: 1 }),
  })

  it('approves a request and reloads the list', async () => {
    const user = userEvent.setup({ delay: null })
    let decided = false
    const api = signedInAs(makeMe(), {
      ...admin(),
      [LIST]: () => json(200, decided ? { items: [], total: 0 } : { items: [REQUEST], total: 1 }),
      'POST /group-requests/r1/approve': () => {
        decided = true
        return json(200, { group: { id: 'g2', name: 'Harbour' } })
      },
    })
    renderApp('/member/group-requests')
    const row = (await screen.findByText(/Pia Provider asks to start Harbour/)).closest('li')!
    await user.click(within(row).getByRole('button', { name: 'Approve Harbour' }))
    expect(await screen.findByText(/Harbour was started/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /group-requests/r1/approve')?.body).toEqual({})
    await waitFor(() => expect(screen.queryByText(/Pia Provider asks/)).toBeNull())
  })

  it('declines a request', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...admin(),
      'POST /group-requests/r1/decline': () => json(204),
    })
    renderApp('/member/group-requests')
    await user.click(await screen.findByRole('button', { name: 'Decline Harbour' }))
    expect(await screen.findByText('The request was declined.')).toBeVisible()
    expect(api.count('POST /group-requests/r1/decline')).toBe(1)
  })

  const LEADING = { ...REQUEST, requester_leads_a_group: true }
  const member = (id: string, name: string, status: string) => ({
    id,
    full_name: name,
    status,
    home_group: { id: 'g1', name: 'Riverside' },
    status_set_by: null,
    flagged_for_recheck: false,
  })

  it('asks who leads the requester’s group from that group’s members, and needs a choice', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...as('admin'),
      [LIST]: () => json(200, { items: [LEADING], total: 1 }),
      [GROUP_MEMBERS]: () =>
        json(200, {
          items: [
            member('p9', 'Pia Provider', 'verifier'),
            member('p7', 'Sam Searcher', 'searcher'),
          ],
          total: 2,
        }),
      'POST /group-requests/r1/approve': () => json(200, { group: { id: 'g2', name: 'Harbour' } }),
    })
    renderApp('/member/group-requests')
    expect(await screen.findByText(/Pia Provider leads a .* now/)).toBeVisible()
    await screen.findByRole('option', { name: 'Sam Searcher · Riverside' })
    expect(screen.queryByRole('option', { name: /^Pia Provider/ })).toBeNull()
    expect(screen.queryByRole('option', { name: /Nobody/ })).toBeNull()
    const approve = screen.getByRole('button', { name: 'Approve Harbour' })
    expect(approve).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/Leads the .* of Pia Provider/), 'p7')
    await user.click(approve)
    await screen.findByText(/Harbour was started/)
    expect(api.calls.find((c) => c.key === 'POST /group-requests/r1/approve')?.body).toEqual({
      successor_id: 'p7',
    })
  })

  it('lets the requester’s group close when they are alone in it', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...as('admin'),
      [LIST]: () => json(200, { items: [LEADING], total: 1 }),
      [GROUP_MEMBERS]: () =>
        json(200, { items: [member('p9', 'Pia Provider', 'verifier')], total: 1 }),
      'POST /group-requests/r1/approve': () => json(200, { group: { id: 'g2', name: 'Harbour' } }),
    })
    renderApp('/member/group-requests')
    const approve = await screen.findByRole('button', { name: 'Approve Harbour' })
    await waitFor(() => expect(approve).toBeEnabled())
    await user.click(approve)
    await screen.findByText(/Harbour was started/)
    expect(api.calls.find((c) => c.key === 'POST /group-requests/r1/approve')?.body).toEqual({})
  })

  it('names the church of each request to the OWNER', async () => {
    signedInAs(makeMe(), {
      ...as('owner'),
      [LIST]: () =>
        json(200, {
          items: [
            REQUEST,
            { ...REQUEST, id: 'r2', church: { id: 'church-2', name: 'Hope Church' } },
          ],
          total: 2,
        }),
    })
    renderApp('/member/group-requests')
    expect(await screen.findByText(/Grace Church/)).toBeVisible()
    expect(screen.getByText(/Hope Church/)).toBeVisible()
  })

  it('says so when the request was decided meanwhile, or the name is taken', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...admin(),
      'POST /group-requests/r1/approve': () => apiError(409, 'not_open'),
    })
    renderApp('/member/group-requests')
    await user.click(await screen.findByRole('button', { name: 'Approve Harbour' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/decided already/)
  })

  it('starts a group at once, and refreshes who they are', async () => {
    const user = userEvent.setup({ delay: null })
    let me = makePerson({ status: 'admin' })
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () => json(200, me),
      [LIST]: () => json(200, { items: [], total: 0 }),
      [OWN_MEMBERS]: () => json(200, { items: [], total: 0 }),
      'POST /group-requests': () => {
        me = makePerson({ status: 'admin', home_group: { id: 'g2', name: 'Harbour' } })
        return json(201, {
          request: { ...REQUEST, state: 'approved' },
          group: { id: 'g2', name: 'Harbour' },
        })
      },
    })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'Harbour')
    await user.click(screen.getByRole('button', { name: 'Start it' }))
    expect(await screen.findByText(/Harbour was started and you lead it/)).toBeVisible()
    expect(api.count('GET /me')).toBeGreaterThan(1)
  })
})

describe('more refusals and failures', () => {
  it('puts the other refusals of an approval in words', async () => {
    const user = userEvent.setup({ delay: null })
    for (const [code, words] of [
      ['successor_required', /Choose who leads the .* you lead now/],
      ['requester_unavailable', /no longer in the/],
    ] as const) {
      signedInAs(makeMe(), {
        ...as('admin'),
        [LIST]: () => json(200, { items: [REQUEST], total: 1 }),
        'POST /group-requests/r1/approve': () => apiError(409, code),
      })
      const { unmount } = renderApp('/member/group-requests')
      await user.click(await screen.findByRole('button', { name: 'Approve Harbour' }))
      expect(await screen.findByRole('alert')).toHaveTextContent(words)
      unmount()
    }
  })

  it('offers the ADMIN’s own group members as successors, needs one, and sends the choice', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () =>
        json(200, makePerson({ status: 'admin', leader: { name: 'Nadia Applicant' } })),
      [LIST]: () => json(200, { items: [], total: 0 }),
      [OWN_MEMBERS]: () =>
        json(200, {
          items: [
            {
              id: '22222222-2222-2222-2222-222222222222',
              full_name: 'Nadia Applicant',
              status: 'admin',
              home_group: { id: 'group-1', name: 'Riverside' },
              status_set_by: null,
              flagged_for_recheck: false,
            },
            {
              id: 'p7',
              full_name: 'Sam Searcher',
              status: 'searcher',
              home_group: { id: 'group-1', name: 'Riverside' },
              status_set_by: null,
              flagged_for_recheck: false,
            },
          ],
          total: 2,
        }),
      'POST /group-requests': () =>
        json(201, {
          request: { ...REQUEST, state: 'approved' },
          group: { id: 'g2', name: 'Harbour' },
        }),
    })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'Harbour')
    await screen.findByRole('option', { name: /Sam Searcher/ })
    expect(screen.queryByRole('option', { name: /Nadia Applicant/ })).toBeNull()
    expect(screen.queryByRole('option', { name: /Nobody/ })).toBeNull()
    const start = screen.getByRole('button', { name: 'Start it' })
    expect(start).toBeDisabled()
    await user.selectOptions(screen.getByLabelText(/Leads your current/), 'p7')
    await user.click(start)
    await screen.findByText(/Harbour was started/)
    expect(api.calls.find((c) => c.key === 'POST /group-requests')?.body).toEqual({
      group_name: 'Harbour',
      successor_id: 'p7',
    })
  })

  it('asks no successor of an ADMIN who does not lead the group they belong to', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () => json(200, makePerson({ status: 'admin', leader: { name: 'Lena Leader' } })),
      [LIST]: () => json(200, { items: [], total: 0 }),
      'POST /group-requests': () =>
        json(201, {
          request: { ...REQUEST, state: 'approved' },
          group: { id: 'g2', name: 'Harbour' },
        }),
    })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'Harbour')
    expect(screen.queryByLabelText(/Leads your current/)).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Start it' }))
    await screen.findByText(/Harbour was started/)
    expect(api.count('GET /verifier/members?limit=50&offset=0&home_group_id=group-1')).toBe(0)
    expect(api.calls.find((c) => c.key === 'POST /group-requests')?.body).toEqual({
      group_name: 'Harbour',
    })
  })

  it('keeps Approve off and offers a retry when the group’s members cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(makeMe(), {
      ...as('admin'),
      [LIST]: () => json(200, { items: [{ ...REQUEST, requester_leads_a_group: true }], total: 1 }),
      [GROUP_MEMBERS]: () =>
        ++attempts === 1
          ? apiError(503, 'service_unavailable')
          : json(200, {
              items: [
                {
                  id: 'p7',
                  full_name: 'Sam Searcher',
                  status: 'searcher',
                  home_group: { id: 'g1', name: 'Riverside' },
                  status_set_by: null,
                  flagged_for_recheck: false,
                },
              ],
              total: 1,
            }),
    })
    renderApp('/member/group-requests')
    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.getByRole('button', { name: 'Approve Harbour' })).toBeDisabled()
    expect(screen.queryByRole('option', { name: /Nobody/ })).toBeNull()
    await user.click(retry)
    expect(await screen.findByRole('option', { name: 'Sam Searcher · Riverside' })).toBeVisible()
  })

  it('still says the group was started when refreshing who they are fails', async () => {
    const user = userEvent.setup({ delay: null })
    let started = false
    signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () =>
        started
          ? apiError(503, 'service_unavailable')
          : json(200, makePerson({ status: 'admin', home_group: null })),
      [LIST]: () => json(200, { items: [], total: 0 }),
      [OWN_MEMBERS]: () => json(200, { items: [], total: 0 }),
      'POST /group-requests': () => {
        started = true
        return json(201, {
          request: { ...REQUEST, state: 'approved' },
          group: { id: 'g2', name: 'Harbour' },
        })
      },
    })
    renderApp('/member/group-requests')
    await user.type(await screen.findByLabelText(/^Name of the/), 'Harbour')
    await user.click(screen.getByRole('button', { name: 'Start it' }))
    expect(await screen.findByText(/Harbour was started and you lead it/)).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows an error when the list cannot be loaded', async () => {
    signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () => apiError(503, 'service_unavailable'),
    })
    renderApp('/member/group-requests')
    expect(await screen.findByRole('alert')).toBeVisible()
  })
})

describe('notifications about group requests', () => {
  it('reads each kind in words', async () => {
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'provider' })),
      [NOTES]: () =>
        json(200, {
          items: [
            ['n1', 'group_request_new'],
            ['n2', 'group_request_approved'],
            ['n3', 'group_request_declined'],
            ['n4', 'reinstated'],
          ].map(([id, kind]) => ({
            id,
            kind,
            subject: { name: 'Lena Leader' },
            created_at: '2026-11-12T08:00:00Z',
            read: false,
          })),
          total: 4,
          unread_count: 4,
        }),
    })
    renderApp('/member/notifications')
    expect(await screen.findByText(/Lena Leader asks to start a/)).toBeVisible()
    expect(screen.getByText(/Lena Leader approved your request/)).toBeVisible()
    expect(screen.getByText(/Lena Leader declined your request/)).toBeVisible()
    expect(screen.getByText(/Lena Leader brought you back/)).toBeVisible()
    expect(screen.queryByText('Something happened')).toBeNull()
  })
})
