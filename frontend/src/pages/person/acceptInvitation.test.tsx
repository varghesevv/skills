import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, mockApi, renderApp } from '../../testUtils'

// Made at run time: no token-like text is kept in the source (ADR-0011).
const TOKEN = `link-${crypto.randomUUID()}`
const PASSWORD = `Pw-${crypto.randomUUID()}`
const LOOKUP = 'POST /admin-invitations/lookup'
const ACCEPT = 'POST /admin-invitations/accept'
const INFO = { church_name: 'Hope Church', email_domain: 'example.org' }

async function fill(
  user: ReturnType<typeof userEvent.setup>,
  overrides: Record<string, string> = {},
) {
  const values = {
    full: 'Ada Admin',
    mobile: '+971500000010',
    password: PASSWORD,
    group: 'Harbour',
    ...overrides,
  }
  await user.type(await screen.findByLabelText('Full name'), values.full)
  await user.type(screen.getByLabelText('Mobile number'), values.mobile)
  await user.type(screen.getByLabelText('New password'), values.password)
  await user.type(screen.getByLabelText(/^Name of your first/), values.group)
}

describe('the invitation of an ADMIN', () => {
  it('shows the church and the domain, and sends the token in the body only', async () => {
    const api = mockApi({ [LOOKUP]: () => json(200, INFO) })
    renderApp(`/invite/${TOKEN}`)
    expect(await screen.findByText(/Hope Church/)).toBeVisible()
    expect(screen.getByText(/example\.org/)).toBeVisible()
    const call = api.calls.find((c) => c.key === LOOKUP)!
    expect(call.body).toEqual({ token: TOKEN })
    expect(api.calls.some((c) => c.key.includes(TOKEN))).toBe(false)
    expect(call.headers.get('Authorization')).toBeNull()
  })

  it('says the link does not work for an unknown, used or expired token, with the same words', async () => {
    mockApi({ [LOOKUP]: () => apiError(404, 'not_found') })
    renderApp(`/invite/${TOKEN}`)
    expect(await screen.findByRole('alert')).toHaveTextContent(/does not work/)
    expect(screen.queryByLabelText('Full name')).toBeNull()
  })

  it('accepts with the details and the first group, then points to signing in', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({
      [LOOKUP]: () => json(200, INFO),
      [ACCEPT]: () => json(201, { id: 'p1', church_id: 'c1', status: 'admin' }),
    })
    renderApp(`/invite/${TOKEN}`)
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Accept the invitation' }))
    expect(await screen.findByText(/You are the .* of the/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in')
    expect(api.calls.find((c) => c.key === ACCEPT)?.body).toEqual({
      token: TOKEN,
      full_name: 'Ada Admin',
      mobile_number: '+971500000010',
      password: PASSWORD,
      home_group_name: 'Harbour',
    })
    expect(api.calls.find((c) => c.key === ACCEPT)?.headers.get('Authorization')).toBeNull()
  })

  it('checks the fields before asking the server', async () => {
    const user = userEvent.setup({ delay: null })
    const api = mockApi({ [LOOKUP]: () => json(200, INFO) })
    renderApp(`/invite/${TOKEN}`)
    await fill(user, { full: 'A', mobile: '12', password: 'short', group: 'H' })
    await user.click(screen.getByRole('button', { name: 'Accept the invitation' }))
    expect(await screen.findAllByText(/Enter|Use|at least/i)).not.toHaveLength(0)
    expect(api.count(ACCEPT)).toBe(0)
  })

  it.each([
    ['church_name_taken', 409, /Ask the .* for a new invitation/],
    ['group_name_taken', 409, /Choose another name/],
    ['account_exists', 409, /belongs to an account already/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    mockApi({ [LOOKUP]: () => json(200, INFO), [ACCEPT]: () => apiError(status, code) })
    renderApp(`/invite/${TOKEN}`)
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Accept the invitation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
    expect(screen.getByLabelText('Full name')).toHaveValue('Ada Admin')
  })

  it('shows the link as dead when the token is refused at the end', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({ [LOOKUP]: () => json(200, INFO), [ACCEPT]: () => apiError(404, 'not_found') })
    renderApp(`/invite/${TOKEN}`)
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Accept the invitation' }))
    expect(await screen.findAllByText(/does not work/)).not.toHaveLength(0)
    expect(screen.queryByLabelText('Full name')).toBeNull()
  })

  it('shows the errors the server finds in a field, next to it', async () => {
    const user = userEvent.setup({ delay: null })
    mockApi({
      [LOOKUP]: () => json(200, INFO),
      [ACCEPT]: () =>
        apiError(422, 'validation_error', {
          fields: [{ field: 'mobile_number', message: 'This number is already in use.' }],
        }),
    })
    renderApp(`/invite/${TOKEN}`)
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Accept the invitation' }))
    expect(await screen.findAllByText('This number is already in use.')).not.toHaveLength(0)
  })

  it('says it is checking while the invitation is looked up', async () => {
    mockApi({ [LOOKUP]: () => new Promise(() => {}) as never })
    renderApp(`/invite/${TOKEN}`)
    expect(await screen.findByRole('status')).toBeVisible()
    expect(screen.queryByLabelText('Full name')).toBeNull()
  })

  it('does not call the invitation dead when the lookup fails for another reason, and retries', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    mockApi({
      [LOOKUP]: () => (++attempts === 1 ? apiError(503, 'service_unavailable') : json(200, INFO)),
    })
    renderApp(`/invite/${TOKEN}`)
    const retry = await screen.findByRole('button', { name: 'Try again' })
    expect(screen.queryByText(/does not work/)).toBeNull()
    await user.click(retry)
    expect(await screen.findByText(/Hope Church/)).toBeVisible()
  })
})
