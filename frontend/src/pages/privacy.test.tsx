import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { json, makeMe, makePerson, renderApp, signedInAs } from '../testUtils'

describe('the privacy statement', () => {
  it('is open to a visitor who is not signed in', async () => {
    renderApp('/privacy')
    expect(await screen.findByRole('heading', { name: 'Privacy' })).toBeVisible()
    for (const heading of [
      'What is kept about you',
      'Who can see what',
      'Closing your account',
      'How long it is kept',
      'Messages and notifications on your phone',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeVisible()
    }
  })

  it('says the number is shown only on Reveal, and that every view is recorded', async () => {
    renderApp('/privacy')
    expect(await screen.findByText(/only when they press Reveal/)).toBeVisible()
    expect(screen.getByText(/each view is recorded/)).toBeVisible()
  })

  it('uses the words of the installation, not fixed ones', async () => {
    renderApp('/privacy')
    expect(
      await screen.findByText(/The Owner of this installation|The owner of this installation/i),
    ).toBeVisible()
    // Role words are tokens, never left in the text.
    expect(document.body.textContent).not.toMatch(/\{[A-Za-z_]+\}/)
  })

  it('is linked from the top bar, signed in or not', async () => {
    const visitor = renderApp('/')
    expect(await screen.findByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
    visitor.unmount()
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'searcher' })),
      'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
    })
    renderApp('/member')
    expect(await screen.findByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
  })
})
