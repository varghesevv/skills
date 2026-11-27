import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getRefreshToken } from '../../auth/tokenStore'
import {
  PASSWORD,
  apiError,
  json,
  makeMe,
  makePerson,
  renderApp,
  signedInAs,
  tokens,
} from '../../testUtils'

// Made-up passwords for the form: nothing here is a credential.
const TEMPORARY = `tmp-${crypto.randomUUID()}`
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}

describe('a temporary password from the initial config', () => {
  it('keeps the person on the change-password page, whatever they open', async () => {
    const api = signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'owner', must_change_password: true })),
    })
    renderApp('/member/search')
    expect(await screen.findByRole('heading', { name: 'Choose your own password' })).toBeVisible()
    // Nothing else is asked for: the API would refuse it.
    expect(api.calls.map((call) => call.key)).toEqual(['POST /auth/refresh', 'GET /me'])
  })

  it('opens the app once the password is changed, with the new tokens', async () => {
    const user = userEvent.setup({ delay: null })
    let changed = false
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () =>
        json(200, makePerson({ status: 'verifier', must_change_password: !changed })),
      'POST /auth/change-password': () => {
        changed = true
        return json(200, tokens('new'))
      },
    })
    renderApp('/member')
    await user.type(await screen.findByLabelText('Temporary password'), TEMPORARY)
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Choose your own password' })).toBeNull(),
    )
    expect(api.last('POST /auth/change-password')?.body).toEqual({
      current_password: TEMPORARY,
      new_password: PASSWORD,
    })
    expect(getRefreshToken()).toBe('refresh-new')
  })

  it('explains a wrong temporary password', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ must_change_password: true })),
      'POST /auth/change-password': () => apiError(403, 'invalid_password'),
    })
    renderApp('/member/change-password')
    await user.type(await screen.findByLabelText('Temporary password'), TEMPORARY)
    await user.type(screen.getByLabelText('New password'), PASSWORD)
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The password is not correct.')
  })

  it('checks the new password before sending it', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ must_change_password: true })),
    })
    renderApp('/member/change-password')
    await user.type(await screen.findByLabelText('Temporary password'), TEMPORARY)
    await user.type(screen.getByLabelText('New password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByText('Use at least 10 characters.')).toBeVisible()
    expect(api.count('POST /auth/change-password')).toBe(0)
  })

  it('is not shown to a person whose password is their own', async () => {
    signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () => json(200, makePerson({ status: 'searcher' })),
    })
    renderApp('/member/change-password')
    await waitFor(() =>
      expect(screen.queryByRole('heading', { name: 'Choose your own password' })).toBeNull(),
    )
  })
})
