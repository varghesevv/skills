import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken } from '../../auth/tokenStore'
import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../testUtils'

const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const as = (status: string, routes: Record<string, () => Response> = {}) =>
  signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () => json(200, makePerson({ status: status as 'provider' })),
    ...routes,
  })
// A made-up password for the form: nothing here is a credential.
const PASSWORD = `pw-${crypto.randomUUID()}`

const leave = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: 'I want to leave' }))
  await user.type(screen.getByLabelText('Your password, to confirm'), PASSWORD)
  await user.click(screen.getByRole('button', { name: 'Close my account' }))
}

describe('the account page', () => {
  it.each(['pending', 'searcher', 'provider', 'verifier', 'admin', 'owner'])(
    'is open to a %s, who finds it from the top bar',
    async (status) => {
      as(status)
      const first = renderApp('/member')
      const link = await screen.findByRole('link', { name: 'My account' })
      expect(link).toHaveAttribute('href', '/member/account')
      first.unmount()
      as(status)
      renderApp('/member/account')
      expect(await screen.findByRole('heading', { name: 'My account' })).toBeVisible()
      expect(screen.getByLabelText('Full name')).toBeVisible()
    },
  )

  it('is not offered to a revoked person, who goes home', async () => {
    as('revoked')
    renderApp('/member/account')
    expect(await screen.findByRole('heading', { name: 'No access' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'My account' })).toBeNull()
  })

  it('shows the details and saves a new name and number', async () => {
    const user = userEvent.setup({ delay: null })
    const api = as('searcher', {
      'PUT /me': () =>
        json(
          200,
          makePerson({
            status: 'searcher',
            full_name: 'Nadia Newname',
            mobile_number: '+971501112222',
          }),
        ),
    })
    renderApp('/member/account')
    const name = await screen.findByLabelText('Full name')
    expect(name).toHaveValue('Nadia Applicant')
    expect(screen.getAllByText('n@example.com').length).toBeGreaterThan(1) // the top bar and the page
    await user.clear(name)
    await user.type(name, 'Nadia Newname')
    const mobile = screen.getByLabelText('Mobile number')
    await user.clear(mobile)
    await user.type(mobile, '+971 50 111 2222')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last('PUT /me')?.body).toEqual({
      full_name: 'Nadia Newname',
      mobile_number: '+971501112222',
    })
    expect(screen.getByLabelText('Full name')).toHaveValue('Nadia Newname')
  })

  it('does not call the server with a bad name or number', async () => {
    const user = userEvent.setup({ delay: null })
    const api = as('searcher')
    renderApp('/member/account')
    const name = await screen.findByLabelText('Full name')
    await user.clear(name)
    await user.type(name, 'A')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Enter your name (2 to 200 characters).')).toBeVisible()
    expect(api.count('PUT /me')).toBe(0)
  })

  it('says so when the number belongs to someone else', async () => {
    const user = userEvent.setup({ delay: null })
    const api = as('searcher', { 'PUT /me': () => apiError(409, 'account_exists') })
    renderApp('/member/account')
    const mobile = await screen.findByLabelText('Mobile number')
    await user.clear(mobile)
    await user.type(mobile, '+971509998888')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This mobile number belongs to another account.',
    )
    expect(api.last('PUT /me')?.body).toEqual({
      full_name: 'Nadia Applicant',
      mobile_number: '+971509998888',
    })
  })
})

describe('leaving from the account page', () => {
  it.each(['searcher', 'provider'])(
    'closes the account of a %s, then signs out',
    async (status) => {
      const user = userEvent.setup({ delay: null })
      const api = as(status, { 'DELETE /me': () => json(204) })
      renderApp('/member/account')
      await leave(user)
      await waitFor(() => expect(api.count('DELETE /me')).toBe(1))
      expect(api.last('DELETE /me')?.body).toEqual({ password: PASSWORD })
      expect(await screen.findByRole('link', { name: 'Join' })).toBeVisible()
      expect(getRefreshToken()).toBeNull()
    },
  )

  it('tells a leader to hand their group on first, and stays signed in', async () => {
    const user = userEvent.setup({ delay: null })
    as('verifier', { 'DELETE /me': () => apiError(409, 'leads_a_group') })
    renderApp('/member/account')
    await leave(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(/You lead a home group/)
    expect(getRefreshToken()).not.toBeNull()
  })

  it.each(['admin', 'owner'])('tells an %s to hand the role on first', async (status) => {
    const user = userEvent.setup({ delay: null })
    as(status, { 'DELETE /me': () => apiError(409, 'leads_a_church') })
    renderApp('/member/account')
    await leave(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Hand that role on first/)
  })

  it('puts a wrong password in words', async () => {
    const user = userEvent.setup({ delay: null })
    as('provider', { 'DELETE /me': () => apiError(403, 'invalid_password') })
    renderApp('/member/account')
    await leave(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(/password is not correct/i)
  })

  it('says an account that cannot be closed cannot be', async () => {
    const user = userEvent.setup({ delay: null })
    as('provider', { 'DELETE /me': () => apiError(403, 'account_revoked') })
    renderApp('/member/account')
    await leave(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('This account cannot be closed.')
  })

  it('does not call the server without a password, and can be cancelled', async () => {
    const user = userEvent.setup({ delay: null })
    const api = as('provider')
    renderApp('/member/account')
    await user.click(await screen.findByRole('button', { name: 'I want to leave' }))
    await user.click(screen.getByRole('button', { name: 'Close my account' }))
    expect(api.count('DELETE /me')).toBe(0)
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'I want to leave' })).toHaveFocus()
  })
})
