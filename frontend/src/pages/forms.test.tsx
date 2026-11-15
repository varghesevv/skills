import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { PASSWORD, apiError, json, mockApi, renderApp } from '../testUtils'

const LINK_VALUE = 'abcdefghijklmnop'

describe('password reset', () => {
  it('asks for a reset link, for a person', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({ 'POST /auth/forgot-password': () => json(202, { status: 'accepted' }) })
    renderApp('/forgot-password')
    await user.type(screen.getByLabelText('Email'), 'w@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset link' }))
    expect(await screen.findByRole('status')).toHaveTextContent(/If an account exists/)
    expect(api.last('POST /auth/forgot-password')?.body).toEqual({
      email: 'w@example.com',
      user_type: 'person',
    })
  })

  it('sets a new password using the token from the link', async () => {
    const user = userEvent.setup({ delay: null })
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
    const user = userEvent.setup({ delay: null })
    mockApi({ 'POST /auth/reset-password': () => apiError(400, 'invalid_reset_token') })
    renderApp(`/reset-password?token=${LINK_VALUE}`)
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/)
  })
})
