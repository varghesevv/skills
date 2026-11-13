import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, signedInAs, renderApp } from '../../testUtils'

const NOTES = 'GET /me/notifications?limit=50'
const base = {
  [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }),
  'GET /me/vouch-link': () => json(200, { active: false, expires_at: null }),
  'GET /me/vouches': () => json(200, { items: [] }),
}
const searcher = (extra = {}) =>
  makePerson({ status: 'searcher', requested_status: null, ...extra })

describe('a searcher who wants to offer their skills', () => {
  it('asks, then sees the request, the vouches so far and their own vouch link', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, searcher()),
      'POST /me/apply-provider': () =>
        json(200, searcher({ requested_status: 'provider', vouch_count: 1 })),
    })
    renderApp('/member')
    await user.click(await screen.findByRole('button', { name: 'I want to offer my skills' }))
    expect(await screen.findByText(/with the leader of your home group/)).toBeVisible()
    expect(screen.getByText(/You have 1 vouch so far/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Make a link to share' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'I want to offer my skills' })).toBeNull()
    expect(api.count('POST /me/apply-provider')).toBe(1)
  })

  it('comes back to the request after signing in again', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, searcher({ requested_status: 'provider', vouch_count: 3 })),
    })
    renderApp('/member')
    expect(await screen.findByText(/You have 3 vouches so far/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'I want to offer my skills' })).toBeNull()
  })

  it('says why asking failed', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, searcher()),
      'POST /me/apply-provider': () => apiError(503, 'service_unavailable'),
    })
    renderApp('/member')
    await user.click(await screen.findByRole('button', { name: 'I want to offer my skills' }))
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.getByRole('button', { name: 'I want to offer my skills' })).toBeEnabled()
  })

  it.each(['provider', 'verifier'] as const)('is not offered to a %s', async (status) => {
    signedInAs(makeMe(), { ...base, 'GET /me': () => json(200, makePerson({ status })) })
    renderApp('/member')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.queryByRole('button', { name: 'I want to offer my skills' })).toBeNull()
  })
})

describe('notifications about it', () => {
  it('says what happened for the leader and for the member', async () => {
    signedInAs(makeMe(), {
      ...base,
      'GET /me': () => json(200, searcher()),
      [NOTES]: () =>
        json(200, {
          items: [
            {
              id: 'n1',
              kind: 'provider_application',
              subject: { id: 'p1', name: 'Sam Searcher' },
              created_at: '2026-11-13T09:00:00Z',
              read: false,
            },
            {
              id: 'n2',
              kind: 'provider_declined',
              subject: { id: 'p2', name: 'Lena Leader' },
              created_at: '2026-11-13T08:00:00Z',
              read: true,
            },
          ],
          total: 2,
          unread_count: 1,
        }),
    })
    renderApp('/member/notifications')
    expect(await screen.findByText(/Sam Searcher asks to offer their skills/)).toBeVisible()
    expect(screen.getByText(/Lena Leader declined your request to offer your skills/)).toBeVisible()
  })
})
