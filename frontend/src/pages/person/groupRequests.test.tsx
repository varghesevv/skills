import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../testUtils'

const LIST = 'GET /group-requests?limit=50&offset=0'
const MEMBERS = 'GET /verifier/members?limit=50&offset=0'
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

  it('asks who leads the requester’s group, and sends the choice', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...as('admin'),
      [LIST]: () => json(200, { items: [{ ...REQUEST, requester_leads_a_group: true }], total: 1 }),
      [MEMBERS]: () =>
        json(200, {
          items: [
            {
              id: 'p9',
              full_name: 'Pia Provider',
              status: 'verifier',
              home_group: { id: 'g1', name: 'Riverside' },
              status_set_by: null,
              flagged_for_recheck: false,
            },
            {
              id: 'p7',
              full_name: 'Sam Searcher',
              status: 'searcher',
              home_group: { id: 'g1', name: 'Riverside' },
              status_set_by: null,
              flagged_for_recheck: false,
            },
          ],
          total: 2,
        }),
      'POST /group-requests/r1/approve': () => json(200, { group: { id: 'g2', name: 'Harbour' } }),
    })
    renderApp('/member/group-requests')
    expect(await screen.findByText(/Pia Provider leads a .* now/)).toBeVisible()
    await screen.findByRole('option', { name: 'Sam Searcher · Riverside' })
    expect(screen.queryByRole('option', { name: /^Pia Provider/ })).toBeNull()
    await user.selectOptions(screen.getByLabelText(/Leads your current/), 'p7')
    await user.click(screen.getByRole('button', { name: 'Approve Harbour' }))
    await screen.findByText(/Harbour was started/)
    expect(api.calls.find((c) => c.key === 'POST /group-requests/r1/approve')?.body).toEqual({
      successor_id: 'p7',
    })
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
      [MEMBERS]: () => json(200, { items: [], total: 0 }),
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
