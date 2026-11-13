import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  PASSWORD,
  apiError,
  json,
  makeMe,
  makePerson,
  mockApi,
  renderApp,
  signedInAs,
  tokens,
} from '../../testUtils'

// Generated for each run: a link token is a secret, so none is written into the source.
const TOKEN = `tok-${Math.random().toString(36).slice(2).padEnd(24, 'x')}`
const NOTES = 'GET /me/notifications?limit=50'
const EMPTY_NOTES = { items: [], total: 0, unread_count: 0 }

const INFO = {
  applicant_name: 'Nadia Applicant',
  church_name: 'Grace Church',
  home_group_name: 'Riverside',
  requested_status: 'provider',
  already_vouched: false,
}

const provider = () => makePerson({ status: 'provider', full_name: 'Pia Provider' })

describe('sharing my vouch link', () => {
  const base = {
    'GET /me/vouches': () => json(200, { items: [] }),
    [NOTES]: () => json(200, EMPTY_NOTES),
    // The change-of-choice form on the same page asks for these.
    'GET /churches': () => json(200, { items: [{ id: 'church-1', name: 'Grace Church' }] }),
    'GET /churches/church-1/home-groups': () =>
      json(200, { items: [{ id: 'group-1', name: 'Riverside', leader_name: 'Lena Leader' }] }),
  }

  it('shows the link once when it is made, and says it will not be shown again', async () => {
    const user = userEvent.setup({ delay: null })
    let active = false
    const api = signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, makePerson()),
      'GET /me/vouch-link': () =>
        json(
          200,
          active ? { active, expires_at: '2026-12-20T10:00:00Z' } : { active, expires_at: null },
        ),
      'POST /me/vouch-link': () => {
        active = true
        return json(201, { token: TOKEN, expires_at: '2026-12-20T10:00:00Z' })
      },
    })
    renderApp('/member')
    expect(await screen.findByText('You have no link that works yet.')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Make a link to share' }))

    const field = await screen.findByLabelText('Your vouch link')
    expect(field).toHaveValue(`${window.location.origin}/vouch/${TOKEN}`)
    expect(screen.getByText('Copy this link now. It is not shown again.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Copy the link' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Make a new link' })).toBeVisible()
    expect(api.count('POST /me/vouch-link')).toBe(1)
  })

  it('does not show the token again after a reload, only that a link works', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, makePerson()),
      'GET /me/vouch-link': () => json(200, { active: true, expires_at: '2026-12-20T10:00:00Z' }),
    })
    renderApp('/member')
    expect(await screen.findByText(/You have a link that works until/)).toBeVisible()
    expect(screen.queryByLabelText('Your vouch link')).toBeNull()
    expect(screen.getByRole('button', { name: 'Make a new link' })).toBeVisible()
  })

  it('says why making a link failed', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, makePerson()),
      'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
      'POST /me/vouch-link': () => apiError(429, 'rate_limited', {}, { 'Retry-After': '120' }),
    })
    renderApp('/member')
    await user.click(await screen.findByRole('button', { name: 'Make a link to share' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many/i)
  })

  it('lists the vouches received and marks the ones that no longer count', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, makePerson({ vouch_count: 1 })),
      'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
      'GET /me/vouches': () =>
        json(200, {
          items: [
            {
              id: 'v1',
              voucher_name: 'Vera Voucher',
              church_name: 'Hope Church',
              live: true,
              created_at: '2026-11-13T08:00:00Z',
            },
            {
              id: 'v2',
              voucher_name: 'Old Voucher',
              church_name: 'Grace Church',
              live: false,
              created_at: '2026-11-12T08:00:00Z',
            },
          ],
        }),
    })
    renderApp('/member')
    const section = (await screen.findByRole('heading', { name: 'Vouches received' })).closest(
      'section',
    )!
    expect(await within(section).findByText(/Vera Voucher, Hope Church/)).toBeVisible()
    expect(within(section).getByText(/Old Voucher, Grace Church/)).toBeVisible()
    expect(within(section).getAllByText(/does not count now/)).toHaveLength(1)
  })
})

describe('the page a vouch link opens', () => {
  const routes = {
    [NOTES]: () => json(200, EMPTY_NOTES),
    'POST /vouch-links/lookup': () => json(200, INFO),
  }

  it('shows who asks and vouches with the token in the body, not the address', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, provider()),
      'POST /vouch-links/vouch': () => json(201, { id: 'v1' }),
    })
    renderApp(`/vouch/${TOKEN}`)
    expect(await screen.findByText(/Nadia Applicant from Grace Church, Riverside/)).toBeVisible()
    expect(api.last('POST /vouch-links/lookup')?.body).toEqual({ token: TOKEN })
    expect(api.calls.every((call) => !call.key.includes(TOKEN))).toBe(true)

    await user.click(screen.getByRole('button', { name: 'I vouch for Nadia Applicant' }))
    expect(await screen.findByText('Thank you. You vouched for Nadia Applicant.')).toBeVisible()
    expect(api.last('POST /vouch-links/vouch')?.body).toEqual({ token: TOKEN })
  })

  it('says so when the person has already vouched', async () => {
    signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, provider()),
      'POST /vouch-links/lookup': () => json(200, { ...INFO, already_vouched: true }),
    })
    renderApp(`/vouch/${TOKEN}`)
    expect(await screen.findByText('You have already vouched for Nadia Applicant.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /I vouch for/ })).toBeNull()
  })

  it.each([
    [404, 'not_found', /not valid any more/],
    [403, 'cannot_vouch_self', /your own link/],
  ])('explains a refused lookup (%s %s)', async (status, code, text) => {
    signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, provider()),
      'POST /vouch-links/lookup': () => apiError(status, code),
    })
    renderApp(`/vouch/${TOKEN}`)
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })

  it.each([
    [409, 'already_vouched', /already vouched for Nadia Applicant/],
    [429, 'rate_limited', /vouched many times today/],
    [404, 'not_found', /not valid any more/],
  ])('explains a refused vouch (%s %s)', async (status, code, text) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...routes,
      'GET /me': () => json(200, provider()),
      'POST /vouch-links/vouch': () => apiError(status, code),
    })
    renderApp(`/vouch/${TOKEN}`)
    await user.click(await screen.findByRole('button', { name: /I vouch for/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })

  it('tells an applicant that only admitted people can vouch, without asking the server', async () => {
    const api = signedInAs(makeMe(), { ...routes, 'GET /me': () => json(200, makePerson()) })
    renderApp(`/vouch/${TOKEN}`)
    expect(await screen.findByText(/Only people who have been admitted can vouch/)).toBeVisible()
    expect(api.count('POST /vouch-links/lookup')).toBe(0)
  })

  it('sends a visitor to sign in and then back to the link', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      ...routes,
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () => json(200, provider()),
    })
    renderApp(`/vouch/${TOKEN}`)
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
    await user.type(screen.getByLabelText('Email'), 'p@example.com')
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText(/Nadia Applicant from Grace Church/)).toBeVisible()
    expect(api.count('POST /vouch-links/lookup')).toBe(1)
  })
})

describe('the vouches I gave', () => {
  it('lists them and withdraws one that can still be withdrawn', async () => {
    const user = userEvent.setup({ delay: null })
    let withdrawn = false
    const api = signedInAs(makeMe(), {
      [NOTES]: () => json(200, EMPTY_NOTES),
      'GET /me': () => json(200, provider()),
      'GET /me/vouches-given': () =>
        json(200, {
          items: [
            {
              id: 'g1',
              applicant_name: 'Nadia Applicant',
              applicant_status: 'pending',
              requested_status: 'searcher',
              withdrawn,
              can_withdraw: !withdrawn,
              created_at: '2026-11-13T08:00:00Z',
            },
            {
              id: 'g2',
              applicant_name: 'Sam Searcher',
              applicant_status: 'searcher',
              requested_status: null,
              withdrawn: false,
              can_withdraw: false,
              created_at: '2026-11-10T08:00:00Z',
            },
          ],
        }),
      'DELETE /vouches/g1': () => {
        withdrawn = true
        return json(204)
      },
    })
    renderApp('/member/vouches')
    expect(await screen.findByText(/Sam Searcher: decided/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Withdraw my vouch for Nadia Applicant' }))
    expect(await screen.findByText(/Nadia Applicant: withdrawn/)).toBeVisible()
    expect(api.count('DELETE /vouches/g1')).toBe(1)
    expect(screen.queryByRole('button', { name: /Withdraw my vouch/ })).toBeNull()
  })

  it('is reached from the home of an admitted person', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      [NOTES]: () => json(200, EMPTY_NOTES),
      'GET /me': () => json(200, provider()),
      'GET /me/vouches-given': () => json(200, { items: [] }),
    })
    renderApp('/member')
    await user.click(await screen.findByRole('link', { name: 'Vouches I gave' }))
    expect(await screen.findByText('You have not vouched for anyone.')).toBeVisible()
  })
})

describe('notifications', () => {
  const NOTE_LIST = {
    items: [
      {
        id: 'n1',
        kind: 'vouch_received',
        subject: { id: 'p1', name: 'Vera Voucher' },
        created_at: '2026-11-13T09:00:00Z',
        read: false,
      },
      {
        id: 'n2',
        kind: 'admitted',
        subject: { id: 'p2', name: 'Lena Leader' },
        created_at: '2026-11-13T08:00:00Z',
        read: true,
      },
      {
        id: 'n3',
        kind: 'applicant_new',
        subject: { id: 'p3', name: '' },
        created_at: '2026-11-12T08:00:00Z',
        read: false,
      },
      {
        id: 'n4',
        kind: 'something_new',
        subject: null,
        created_at: '2026-11-11T08:00:00Z',
        read: true,
      },
    ],
    total: 4,
    unread_count: 2,
  }

  it('shows the count in the top bar and the list with a line for each kind', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      [NOTES]: () => json(200, NOTE_LIST),
      'GET /me': () => json(200, provider()),
    })
    renderApp('/member')
    await user.click(await screen.findByRole('link', { name: 'Notifications (2 unread)' }))
    expect(await screen.findByText(/Vera Voucher vouched for you/)).toBeVisible()
    expect(screen.getByText(/Lena Leader admitted you/)).toBeVisible()
    expect(screen.getByText(/Someone chose your/)).toBeVisible() // a closed account has no name
    expect(screen.getByText(/Something happened/)).toBeVisible() // a kind this version does not know
  })

  it('marks one as read and then all', async () => {
    const user = userEvent.setup({ delay: null })
    let list = NOTE_LIST
    const api = signedInAs(makeMe(), {
      [NOTES]: () => json(200, list),
      'GET /me': () => json(200, provider()),
      'POST /me/notifications/n1/read': () => {
        list = {
          ...list,
          unread_count: 1,
          items: list.items.map((i) => (i.id === 'n1' ? { ...i, read: true } : i)),
        }
        return json(204)
      },
      'POST /me/notifications/read-all': () => {
        list = { ...list, unread_count: 0, items: list.items.map((i) => ({ ...i, read: true })) }
        return json(204)
      },
    })
    renderApp('/member/notifications')
    const first = (await screen.findByText(/Vera Voucher vouched for you/)).closest('li')!
    await user.click(
      within(first).getByRole('button', { name: /^Mark as read: Vera Voucher vouched for you/ }),
    )
    expect(await screen.findByRole('link', { name: 'Notifications (1 unread)' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Mark all as read' }))
    expect(await screen.findByRole('link', { name: 'Notifications' })).toBeVisible()
    expect(api.count('POST /me/notifications/read-all')).toBe(1)
    expect(screen.queryByRole('button', { name: 'Mark all as read' })).toBeNull()
  })

  it('says when there is nothing new', async () => {
    signedInAs(makeMe(), {
      [NOTES]: () => json(200, EMPTY_NOTES),
      'GET /me': () => json(200, provider()),
    })
    renderApp('/member/notifications')
    expect(await screen.findByText('Nothing new.')).toBeVisible()
  })

  it('shows an error with a retry when the list cannot be loaded', async () => {
    signedInAs(makeMe(), {
      [NOTES]: () => apiError(500, 'server_error'),
      'GET /me': () => json(200, provider()),
    })
    renderApp('/member/notifications')
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeVisible()
  })

  it('is not asked for by a revoked person', async () => {
    const api = signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'revoked', home_group: null, leader: null })),
    })
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'No access' })).toBeVisible()
    expect(api.count(NOTES)).toBe(0)
    expect(screen.queryByRole('link', { name: /Notifications/ })).toBeNull()
  })
})

describe('an applicant on the page of vouches given', () => {
  it('is sent home without a request, because only admitted people vouch', async () => {
    const api = signedInAs(makeMe(), {
      [NOTES]: () => json(200, EMPTY_NOTES),
      'GET /me': () => json(200, makePerson()),
      'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
      'GET /me/vouches': () => json(200, { items: [] }),
      'GET /churches': () => json(200, { items: [] }),
    })
    renderApp('/member/vouches')
    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
    expect(api.count('GET /me/vouches-given')).toBe(0)
  })
})

describe('a revoked person on the pages for members', () => {
  it.each(['/member/notifications', '/member/vouches'])(
    'is sent home from %s without a request',
    async (path) => {
      const api = signedInAs(makeMe(), {
        'GET /me': () =>
          json(200, makePerson({ status: 'revoked', home_group: null, leader: null })),
      })
      renderApp(path)
      expect(await screen.findByRole('heading', { name: 'No access' })).toBeVisible()
      expect(api.count(NOTES)).toBe(0)
      expect(api.count('GET /me/vouches-given')).toBe(0)
    },
  )
})
