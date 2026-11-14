import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'
import { ALL_LABELS, ME_ID, makeProfile } from '../../../portals/freelancer/testData'

const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const as = (status: string, routes: Record<string, () => Response> = {}) =>
  signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () => json(200, makePerson({ status: status as 'provider', id: ME_ID })),
    ...routes,
  })

describe('the provider menu', () => {
  it.each(['provider', 'verifier', 'admin', 'owner'])('is shown to a %s', async (status) => {
    as(status)
    renderApp('/member')
    const nav = await screen.findByRole('navigation', { name: 'My profile' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Profile', 'Skills and labels', 'Availability', 'My ratings'])
  })

  it.each(['pending', 'searcher'])('is not shown to a %s', async (status) => {
    as(status)
    renderApp('/member')
    await screen.findByRole('link', { name: /Notifications/ })
    expect(screen.queryByRole('navigation', { name: 'My profile' })).toBeNull()
  })
})

describe('who may open the provider pages', () => {
  it.each(['/member/profile', '/member/skills', '/member/availability', '/member/ratings'])(
    'sends a searcher from %s to their home without asking for a profile',
    async (path) => {
      const api = as('searcher')
      renderApp(path)
      expect(await screen.findByText(/^Welcome/)).toBeVisible()
      expect(api.calls.some((c) => c.key.includes('/freelancers/'))).toBe(false)
    },
  )

  it('sends an applicant home too', async () => {
    as('pending')
    renderApp('/member/profile')
    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
  })

  it.each(['provider', 'verifier', 'admin'])(
    'keeps the labels of the OWNER from a %s',
    async (status) => {
      const api = as(status)
      renderApp('/member/labels')
      expect(await screen.findByText(/^Welcome/)).toBeVisible()
      expect(api.calls.some((c) => c.key.startsWith('GET /labels'))).toBe(false)
    },
  )
})

describe('the provider pages', () => {
  it('shows and saves the profile of the person', async () => {
    const ui = userEvent.setup({ delay: null })
    const api = as('provider', {
      'GET /freelancers/me': () => json(200, makeProfile()),
      'PUT /freelancers/me': () =>
        json(200, makeProfile({ nationality: 'Indian', rate_per_hour: 30, rate_currency: 'AED' })),
    })
    renderApp('/member/profile')
    expect(await screen.findByLabelText('Full name')).toHaveValue('Fatima Khan')
    await ui.type(screen.getByLabelText('Rate per hour'), '30')
    await ui.type(screen.getByLabelText('Currency'), 'AED')
    await ui.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last('PUT /freelancers/me')?.body).toMatchObject({
      rate_per_hour: 30,
      rate_currency: 'AED',
    })
  })

  it('shows the skills and labels of the person', async () => {
    as('verifier', {
      'GET /freelancers/me': () => json(200, makeProfile()),
      'GET /labels': () => json(200, ALL_LABELS),
    })
    renderApp('/member/skills')
    expect(await screen.findByRole('heading', { name: /Skills and labels/ })).toBeVisible()
    expect(await screen.findByText('plumbing')).toBeVisible()
  })

  it('shows the unavailability of the person', async () => {
    as('admin', {
      'GET /freelancers/me/unavailability': () =>
        json(200, [
          {
            id: 'u1',
            unavailable_from: '2030-01-10T00:00:00Z',
            unavailable_to: '2030-01-12T00:00:00Z',
          },
        ]),
    })
    renderApp('/member/availability')
    expect(await screen.findByRole('heading', { name: /Availability/ })).toBeVisible()
  })

  it('lists the ratings the person received', async () => {
    const api = as('provider', {
      [`GET /freelancers/${ME_ID}/ratings?page=1&page_size=10`]: () =>
        json(200, {
          items: [{ rating: 9, comment: 'Very good', rated_on: '2026-11-01T10:00:00Z' }],
          total: 1,
          page: 1,
          page_size: 10,
        }),
    })
    renderApp('/member/ratings')
    expect(await screen.findByText('Very good')).toBeVisible()
    expect(api.count(`GET /freelancers/${ME_ID}/ratings?page=1&page_size=10`)).toBe(1)
  })
})

describe('the labels of the OWNER', () => {
  it('lists every label, including the inactive, for the OWNER', async () => {
    const api = as('owner', {
      'GET /labels?include_inactive=true': () => json(200, ALL_LABELS),
    })
    renderApp('/member/labels')
    expect(await screen.findByText('plumbing')).toBeVisible()
    expect(api.count('GET /labels?include_inactive=true')).toBe(1)
    expect(screen.getByRole('link', { name: 'Labels' })).toBeVisible()
  })
})
