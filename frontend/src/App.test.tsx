import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken, setTokens } from './auth/tokenStore'
import { PASSWORD, apiError, json, makeMe, mockApi, renderApp, tokens } from './testUtils'

const OLD_REFRESH = 'refresh-old'

async function fillLogin(user: ReturnType<typeof userEvent.setup>, email = 'f@example.com') {
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), PASSWORD)
}

/** A returning visitor: a refresh token is stored, so the app restores the session. */
function signedInAs(me = makeMe()) {
  setTokens('gone', OLD_REFRESH)
  return mockApi({
    'POST /auth/refresh': () => json(200, tokens('2')),
    'GET /me': () => json(200, me),
    'POST /auth/logout': () => json(204),
  })
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

  it('sends the chosen account type', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      'POST /auth/login': () => json(200, tokens('1')),
      'GET /me': () =>
        json(200, makeMe({ user_type: 'admin', email: 'a@example.com', full_name: null })),
    })
    renderApp('/login')
    await user.selectOptions(screen.getByLabelText('I am a'), 'admin')
    await fillLogin(user, 'a@example.com')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Welcome, a@example.com' })).toBeVisible()
    expect(api.last('POST /auth/login')?.body).toMatchObject({ user_type: 'admin' })
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
    renderApp('/login?type=organisation')
    expect(screen.getByLabelText('I am a')).toHaveValue('organisation')
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
