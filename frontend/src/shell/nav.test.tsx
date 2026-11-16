import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { PersonStatus } from '../api/types'
import { json, makeMe, makePerson, renderApp, signedInAs } from '../testUtils'
import { atLeast, navFor } from './nav'

// docs/design-system.md, section 2.2: what each status sees in the top bar.

const STATUSES: PersonStatus[] = [
  'revoked',
  'pending',
  'searcher',
  'provider',
  'verifier',
  'admin',
  'owner',
]

/** The group ids each status must have, and so which it must not. */
const GROUPS: Record<PersonStatus, string[]> = {
  revoked: [],
  pending: [],
  searcher: ['find'],
  provider: ['find', 'services'],
  verifier: ['find', 'services', 'church'],
  admin: ['find', 'services', 'church', 'admin'],
  owner: ['find', 'services', 'church', 'admin', 'owner'],
}

describe('navFor', () => {
  it.each(STATUSES)('gives a %s exactly its own groups, in order', (status) => {
    const person = makePerson({ status })
    expect(navFor(person).map((group) => group.id)).toEqual(GROUPS[status])
  })

  it('never lists a link twice, whatever the status', () => {
    for (const status of STATUSES) {
      const links = navFor(makePerson({ status })).flatMap((group) => group.links.map((l) => l.to))
      expect(new Set(links).size).toBe(links.length)
    }
  })

  it('offers the invitation link only to a leader of a group', () => {
    const leads = makePerson({ status: 'verifier', full_name: 'Lena Leader' })
    const other = makePerson({ status: 'verifier', full_name: 'Someone Else' })
    const church = (p: typeof leads) =>
      navFor(p)
        .find((group) => group.id === 'church')
        ?.links.map((l) => l.to)
    expect(church(leads)).toContain('/member/invitations')
    expect(church(other)).not.toContain('/member/invitations')
  })

  it('keeps the owner screens to the owner and the reports to an admin and above', () => {
    const paths = (status: PersonStatus) =>
      navFor(makePerson({ status })).flatMap((group) => group.links.map((l) => l.to))
    expect(paths('admin')).toContain('/member/reports')
    expect(paths('admin')).not.toContain('/member/churches')
    expect(paths('owner')).toContain('/member/churches')
    expect(paths('verifier')).not.toContain('/member/reports')
  })

  it('orders the statuses, and puts a revoked or pending person below every one', () => {
    expect(atLeast({ status: 'provider' }, 'searcher')).toBe(true)
    expect(atLeast({ status: 'searcher' }, 'provider')).toBe(false)
    expect(atLeast({ status: 'revoked' }, 'searcher')).toBe(false)
    expect(atLeast({ status: 'pending' }, 'searcher')).toBe(false)
  })
})

const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 2 }),
}
const as = (status: PersonStatus) =>
  signedInAs(makeMe(), { ...quiet, 'GET /me': () => json(200, makePerson({ status })) })

describe('the top bar', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows a group as a button that opens and closes its links', async () => {
    const user = userEvent.setup()
    as('provider')
    renderApp('/member')
    const button = await screen.findByRole('button', { name: 'My services' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard('{Escape}')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveFocus()
  })

  it('has no My services for a searcher and no Leader menu for a provider', async () => {
    as('searcher')
    renderApp('/member')
    await screen.findByRole('link', { name: /Notifications/ })
    expect(screen.queryByRole('button', { name: 'My services' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Leader' })).toBeNull()
  })

  it('shows a revoked person only privacy and log out', async () => {
    as('revoked')
    renderApp('/member')
    await screen.findByRole('button', { name: 'Log out' })
    expect(screen.getByRole('link', { name: 'Privacy' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Notifications/ })).toBeNull()
    expect(screen.queryByRole('link', { name: 'My account' })).toBeNull()
  })

  it('searches by name from the bar', async () => {
    const user = userEvent.setup()
    as('searcher')
    renderApp('/member')
    await user.type(await screen.findByLabelText('Search by name'), 'anita')
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { level: 1, name: /Find/ })).toBeInTheDocument()
    // The search page has its own name field, which now carries the name.
    expect(screen.getByLabelText('Search by name')).toHaveValue('anita')
  })

  it('on a phone puts the groups behind one Menu button, open, under headings', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }))
    const user = userEvent.setup()
    as('verifier')
    renderApp('/member')
    const menu = await screen.findByRole('button', { name: 'Menu' })
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById('site-menu')).toHaveAttribute('data-open', 'false')
    await user.click(menu)
    const panel = document.getElementById('site-menu') as HTMLElement
    expect(panel).toHaveAttribute('data-open', 'true')
    // Headings, not buttons: no second tap to reach a link.
    expect(within(panel).getByRole('heading', { name: 'Leader' })).toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: 'Leader' })).toBeNull()
    expect(within(panel).getByRole('link', { name: 'Applicants' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(menu).toHaveAttribute('aria-expanded', 'false')
    expect(menu).toHaveFocus()
  })
})

describe('the tiles of the member home', () => {
  it.each([
    ['searcher', ['Find freelancers', 'Vouches I gave']],
    ['provider', ['Find freelancers', 'Profile', 'Vouches I gave']],
  ] as const)('are ordered for a %s, the search first', async (status, first) => {
    as(status)
    renderApp('/member')
    await screen.findByRole('heading', { level: 1 })
    const tiles = [...document.querySelectorAll('.tiles a')].map((a) => a.textContent)
    expect(tiles.slice(0, first.length)).toEqual(first)
  })
})
