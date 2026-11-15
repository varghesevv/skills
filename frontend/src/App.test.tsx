import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken } from './auth/tokenStore'
import {
  OLD_REFRESH,
  json,
  makeMe,
  makePerson,
  mockApi,
  renderApp,
  signedInAs,
  tokens,
} from './testUtils'

const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const asPerson = (status: string = 'searcher') =>
  signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () =>
      json(200, makePerson({ status: status as 'searcher', full_name: 'Sam Searcher' })),
  })

describe('public pages', () => {
  it('offers to sign up and to sign in on the landing page', async () => {
    mockApi({})
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/find skilled/i)
    const signUp = screen.getAllByRole('link', { name: 'Join' }).map((l) => l.getAttribute('href'))
    expect(signUp).toContain('/sign-up')
    const signIn = screen
      .getAllByRole('link', { name: 'Sign in' })
      .map((l) => l.getAttribute('href'))
    expect(signIn).toContain('/sign-in')
  })

  it('shows a not-found page', async () => {
    mockApi({})
    renderApp('/nothing-here')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it.each(['/login', '/login/admin', '/login/church', '/register', '/register/freelancer'])(
    'moves the older address %s to the sign-in or the sign-up',
    async (path) => {
      mockApi({})
      renderApp(path)
      const heading = path.startsWith('/register') ? 'Join' : 'Sign in'
      expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    },
  )
})

describe('protected pages', () => {
  it.each(['/member', '/member/search', '/member/reports', '/member/account'])(
    'sends a visitor from %s to sign in',
    async (path) => {
      mockApi({})
      renderApp(path)
      expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    },
  )

  it('restores the session after a reload using the refresh token', async () => {
    const api = asPerson()
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Welcome, Sam Searcher' })).toBeVisible()
    expect(api.last('POST /auth/refresh')?.body).toEqual({ refresh_token: OLD_REFRESH })
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('does not open anything for a token of an account of the older kind', async () => {
    signedInAs(makeMe({ user_type: 'workhost' }), { ...quiet })
    renderApp('/member')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('logs out: revokes the token, forgets it and returns to the sign-in page', async () => {
    const user = userEvent.setup({ delay: null })
    const api = asPerson()
    renderApp('/member')
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(api.last('POST /auth/logout')?.body).toEqual({
      refresh_token: tokens('2').refresh_token,
    })
    expect(getRefreshToken()).toBeNull()
  })
})
