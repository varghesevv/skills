import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken } from './auth/tokenStore'
import {
  OLD_REFRESH,
  PASSWORD,
  apiError,
  json,
  makeMe,
  mockApi,
  renderApp,
  signedInAs,
  tokens,
} from './testUtils'

async function fillLogin(user: ReturnType<typeof userEvent.setup>, email = 'f@example.com') {
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), PASSWORD)
}

describe('public pages', () => {
  it('offers the three kinds of account on the landing page', async () => {
    mockApi({})
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(/find skilled/i)
    const hrefs = screen
      .getAllByRole('link', { name: 'Register' })
      .map((link) => link.getAttribute('href'))
    expect(hrefs).toEqual(
      expect.arrayContaining([
        '/register/freelancer',
        '/register/workhost',
        '/register/organisation',
      ]),
    )
  })

  it('shows a not-found page', async () => {
    mockApi({})
    renderApp('/nothing-here')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})

describe('login', () => {
  it('logs in and lands on the dashboard of the persons portal', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () => json(200, makeMe()),
    })
    renderApp('/login')
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('heading', { name: 'Welcome, Fatima Khan' })).toBeVisible()
    expect(api.last('POST /auth/login')?.body).toEqual({
      email: 'f@example.com',
      password: PASSWORD,
      user_type: 'freelancer',
    })
    expect(api.last('GET /me')?.headers.get('Authorization')).toBe('Bearer access-1')
    expect(getRefreshToken()).toBe('refresh-1')
  })

  it('lets work hosts log in from the same page with a link instead of a dropdown', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () => json(200, makeMe({ user_type: 'workhost', full_name: 'Wael Host' })),
    })
    renderApp('/login')
    expect(screen.queryByLabelText('I am a')).not.toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Log in as' })
    expect(within(nav).getByRole('link', { name: 'Freelancer' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await user.click(within(nav).getByRole('link', { name: 'Work host' }))
    expect(within(nav).getByRole('link', { name: 'Work host' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    await fillLogin(user, 'w@example.com')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Welcome, Wael Host' })).toBeVisible()
    expect(api.last('POST /auth/login')?.body).toMatchObject({ user_type: 'workhost' })
  })

  it('has an admin page that only logs in admins', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () =>
        json(200, makeMe({ user_type: 'admin', email: 'a@example.com', full_name: null })),
    })
    renderApp('/login/admin')
    expect(screen.getByRole('heading', { name: 'Admin log in' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Register' })).not.toBeInTheDocument()
    await fillLogin(user, 'a@example.com')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Welcome, a@example.com' })).toBeVisible()
    expect(api.last('POST /auth/login')?.body).toMatchObject({ user_type: 'admin' })
  })

  it('has an organisation page that only logs in organisations and links to its sign-up', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({ 'POST /auth/login': () => apiError(401, 'invalid_credentials') })
    renderApp('/login/organisation')
    expect(screen.getByRole('heading', { name: 'Organisation log in' })).toBeInTheDocument()
    expect(screen.queryByLabelText('I am a')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Register' })).toHaveAttribute(
      'href',
      '/register/organisation',
    )
    await fillLogin(user, 'o@example.com')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await screen.findByRole('alert')
    expect(api.last('POST /auth/login')?.body).toMatchObject({ user_type: 'organisation' })
  })

  it('moves an old /login?type=organisation link to the organisation page', async () => {
    mockApi({})
    renderApp('/login?type=organisation')
    expect(await screen.findByRole('heading', { name: 'Organisation log in' })).toBeInTheDocument()
  })

  it('shows one message for a wrong password and stays on the page', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ 'POST /auth/login': () => apiError(401, 'invalid_credentials') })
    renderApp('/login')
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('explains that an organisation is waiting for approval', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ 'POST /auth/login': () => apiError(403, 'organisation_pending') })
    renderApp('/login/organisation')
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/waiting for admin approval/)
  })

  it('tells the person how long to wait after too many attempts', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({
      'POST /auth/login': () => apiError(429, 'too_many_attempts', {}, { 'Retry-After': '120' }),
    })
    renderApp('/login')
    await fillLogin(user)
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 2 minute(s).')
  })

  it('checks the form before calling the API', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({})
    renderApp('/login')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findAllByText('This field is required.')).toHaveLength(2)
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(api.calls).toHaveLength(0)
  })

  it('can show and hide the password', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({})
    renderApp('/login')
    const field = screen.getByLabelText('Password')
    expect(field).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(field).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})

describe('protected pages', () => {
  it('sends a visitor to the login page', async () => {
    mockApi({})
    renderApp('/freelancer')
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('sends a visitor to the login page that fits the address', async () => {
    mockApi({})
    renderApp('/organisation')
    expect(await screen.findByRole('heading', { name: 'Organisation log in' })).toBeInTheDocument()
  })

  it('sends a visitor of the admin area to the admin login', async () => {
    mockApi({})
    renderApp('/admin/reports')
    expect(await screen.findByRole('heading', { name: 'Admin log in' })).toBeInTheDocument()
  })

  it('sends a person to their own portal when they open another one', async () => {
    signedInAs(makeMe({ user_type: 'workhost', full_name: 'Wael Host' }))
    renderApp('/freelancer')
    expect(await screen.findByRole('heading', { name: 'Welcome, Wael Host' })).toBeVisible()
    expect(screen.getByText('Work host', { selector: '.role-badge' })).toBeInTheDocument()
  })

  it('restores the session after a reload using the refresh token', async () => {
    const api = signedInAs()
    renderApp('/freelancer')
    expect(await screen.findByRole('heading', { name: 'Welcome, Fatima Khan' })).toBeVisible()
    expect(api.last('POST /auth/refresh')?.body).toEqual({ refresh_token: OLD_REFRESH })
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('shows the organisation name for organisations', async () => {
    signedInAs(
      makeMe({
        user_type: 'organisation',
        full_name: null,
        org_name: 'Acme Training',
        approval_status: 'approved',
      }),
    )
    renderApp('/organisation')
    expect(await screen.findByRole('heading', { name: 'Welcome, Acme Training' })).toBeVisible()
    expect(screen.getByText('Organisation Name')).toBeInTheDocument()
  })

  it('logs out: revokes the token, forgets it and returns to the login page', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs()
    renderApp('/freelancer')
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.last('POST /auth/logout')?.body).toEqual({
      refresh_token: tokens('2').refresh_token,
    })
    expect(getRefreshToken()).toBeNull()
  })
})

describe('navigation drawer', () => {
  it('opens from the menu button and closes with Escape, returning focus to the button', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs()
    renderApp('/freelancer')
    const button = await screen.findByRole('button', { name: 'Open menu' })
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(nav).toHaveAttribute('data-open', 'false')

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(nav).toHaveAttribute('data-open', 'true')
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await user.keyboard('{Escape}')
    expect(nav).toHaveAttribute('data-open', 'false')
    expect(button).toHaveFocus()
  })

  it('closes when the backdrop or the close button is used', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs()
    renderApp('/freelancer')
    const button = await screen.findByRole('button', { name: 'Open menu' })
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })

    await user.click(button)
    await user.click(document.querySelector('.backdrop') as HTMLElement)
    expect(nav).toHaveAttribute('data-open', 'false')

    await user.click(button)
    await user.click(within(nav).getByRole('button', { name: 'Close menu' }))
    expect(nav).toHaveAttribute('data-open', 'false')
  })
})
