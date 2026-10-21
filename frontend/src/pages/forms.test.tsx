import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { PASSWORD, apiError, json, mockApi, renderApp } from '../testUtils'

const LINK_VALUE = 'abcdefghijklmnop'

type User = ReturnType<typeof userEvent.setup>

async function fillAccount(user: User, email: string, mobile: string, name = 'Test Person') {
  if (screen.queryByLabelText('Full name')) {
    await user.type(screen.getByLabelText('Full name'), name)
  }
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Mobile number'), mobile)
  await user.type(screen.getByLabelText('Password'), PASSWORD)
}

describe('registration', () => {
  it('registers a freelancer', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'POST /auth/register/freelancer': () =>
        json(201, {
          id: 'x',
          user_type: 'freelancer',
          email: 'n@example.com',
          approval_status: null,
        }),
    })
    renderApp('/register/freelancer')
    await fillAccount(user, 'n@example.com', '+971 50 000 0002', 'Nadia Ali')
    await user.type(screen.getByLabelText('Nationality (optional)'), 'Indian')
    await user.click(screen.getByLabelText('I am available on WhatsApp'))
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Account created' })).toBeInTheDocument()
    expect(api.last('POST /auth/register/freelancer')?.body).toEqual({
      full_name: 'Nadia Ali',
      email: 'n@example.com',
      mobile_number: '+971500000002',
      password: PASSWORD,
      nationality: 'Indian',
      primary_language: null,
      whatsapp_availability: true,
    })
  })

  it('tells a new organisation that an admin must approve it', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'POST /auth/register/organisation': () =>
        json(201, {
          id: 'x',
          user_type: 'organisation',
          email: 'o@example.com',
          approval_status: 'pending',
        }),
    })
    renderApp('/register/organisation')
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Organisation Name'), 'Acme Training')
    await fillAccount(user, 'o@example.com', '0501234567')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('status')).toHaveTextContent(/waiting for admin approval/)
    const body = api.last('POST /auth/register/organisation')?.body
    expect(body).toMatchObject({ org_name: 'Acme Training' })
    expect(body).not.toHaveProperty('nationality')
    expect(body).not.toHaveProperty('full_name')
  })

  it('does not call the API for a short password', async () => {
    const user = userEvent.setup()
    const api = mockApi({})
    renderApp('/register/workhost')
    await user.type(screen.getByLabelText('Full name'), 'Wael Host')
    await user.type(screen.getByLabelText('Email'), 'w@example.com')
    await user.type(screen.getByLabelText('Mobile number'), '0501234567')
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Use at least 10 characters.')).toBeInTheDocument()
    expect(api.calls).toHaveLength(0)
  })

  it('asks work hosts and freelancers for their name', async () => {
    const user = userEvent.setup()
    const api = mockApi({})
    renderApp('/register/workhost')
    await user.type(screen.getByLabelText('Email'), 'w@example.com')
    await user.type(screen.getByLabelText('Mobile number'), '0501234567')
    await user.type(screen.getByLabelText('Password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Enter your name (2 to 200 characters).')).toBeInTheDocument()
    expect(api.calls).toHaveLength(0)
  })

  it('shows a taken email next to the email field', async () => {
    const user = userEvent.setup()
    mockApi({ 'POST /auth/register/workhost': () => apiError(409, 'email_taken') })
    renderApp('/register/workhost')
    await fillAccount(user, 'w@example.com', '0501234567')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription(
      'An account with this email already exists.',
    )
  })

  it('shows server field messages from a 422', async () => {
    const user = userEvent.setup()
    mockApi({
      'POST /auth/register/workhost': () =>
        apiError(422, 'validation_error', {
          fields: [{ field: 'mobile_number', message: 'mobile number looks wrong' }],
        }),
    })
    renderApp('/register/workhost')
    await fillAccount(user, 'w@example.com', '0501234567')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('mobile number looks wrong')).toBeInTheDocument()
  })

  it('does not offer an admin sign-up', async () => {
    mockApi({})
    renderApp('/register/admin')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})

describe('password reset', () => {
  it('asks for a reset link', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'POST /auth/forgot-password': () => json(202, { status: 'accepted' }) })
    renderApp('/forgot-password')
    await user.selectOptions(screen.getByLabelText('I am a'), 'workhost')
    await user.type(screen.getByLabelText('Email'), 'w@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))
    expect(await screen.findByRole('status')).toHaveTextContent(/If an account exists/)
    expect(api.last('POST /auth/forgot-password')?.body).toEqual({
      email: 'w@example.com',
      user_type: 'workhost',
    })
  })

  it('sets a new password using the token from the link', async () => {
    const user = userEvent.setup()
    const api = mockApi({ 'POST /auth/reset-password': () => json(204) })
    renderApp(`/reset-password?token=${LINK_VALUE}`)
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByRole('status')).toHaveTextContent(/password was changed/)
    expect(api.last('POST /auth/reset-password')?.body).toEqual({
      token: LINK_VALUE,
      new_password: PASSWORD,
    })
  })

  it('asks for a new link when the token is missing', async () => {
    mockApi({})
    renderApp('/reset-password')
    expect(await screen.findByRole('alert')).toHaveTextContent(/incomplete/)
  })

  it('explains an invalid or expired token', async () => {
    const user = userEvent.setup()
    mockApi({ 'POST /auth/reset-password': () => apiError(400, 'invalid_reset_token') })
    renderApp(`/reset-password?token=${LINK_VALUE}`)
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/)
  })
})
