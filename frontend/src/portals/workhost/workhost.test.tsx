import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { json, makeMe, renderApp, signedInAs } from '../../testUtils'
import { ALL_LABELS, label } from '../freelancer/testData'

const ui = () => userEvent.setup({ delay: null })
const host = makeMe({ user_type: 'workhost', full_name: 'Wael Host', email: 'w@example.com' })
const LABELS = [...ALL_LABELS, label('nt1', 'Indian', 'nativity')]

function asHost(routes: Parameters<typeof signedInAs>[1] = {}) {
  return signedInAs(host, { 'GET /labels': () => json(200, LABELS), ...routes })
}

describe('navigation', () => {
  it('lists the work host pages', async () => {
    asHost()
    renderApp('/workhost')
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Dashboard', 'Profile'])
  })
})

describe('profile', () => {
  const profile = {
    id: host.id,
    full_name: 'Wael Host',
    email: 'w@example.com',
    mobile_number: '+971500000002',
    available_days: ['mon', 'tue'],
    created_at: '2026-10-01T10:00:00Z',
  }

  it('shows the saved days and saves changes', async () => {
    const user = ui()
    const api = asHost({
      'GET /workhosts/me': () => json(200, profile),
      'PUT /workhosts/me': () => json(200, { ...profile, available_days: ['mon', 'tue', 'sun'] }),
    })
    renderApp('/workhost/profile')
    expect(await screen.findByLabelText('Monday')).toBeChecked()
    expect(screen.getByLabelText('Wednesday')).not.toBeChecked()

    await user.click(screen.getByLabelText('Sunday'))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last('PUT /workhosts/me')?.body).toEqual({
      full_name: 'Wael Host',
      mobile_number: '+971500000002',
      available_days: ['sun', 'mon', 'tue'],
    })
  })

  it('does not save a bad mobile number', async () => {
    const user = ui()
    const api = asHost({ 'GET /workhosts/me': () => json(200, profile) })
    renderApp('/workhost/profile')
    const mobile = await screen.findByLabelText('Mobile number')
    await user.clear(mobile)
    await user.type(mobile, 'abc')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/Enter 7 to 15 digits/)).toBeVisible()
    expect(api.count('PUT /workhosts/me')).toBe(0)
  })
})
