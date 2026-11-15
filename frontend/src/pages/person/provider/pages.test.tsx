import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'
import { sortLevels } from './LabelsPage'
import {
  ALL_LABELS,
  BASIC,
  CARPENTRY,
  EIGHTY,
  ENGLISH,
  HALF,
  ME_ID,
  PLUMBING,
  label,
  makeProfile,
} from './testData'

const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
/** A PROVIDER on their own pages. */
function asProvider(routes: Record<string, () => Response> = {}) {
  return signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () => json(200, makePerson({ status: 'provider', id: ME_ID })),
    ...routes,
  })
}

const user = () => userEvent.setup({ delay: null })

describe('profile page', () => {
  it('shows the saved profile and saves changes in the shape the API expects', async () => {
    const ui = user()
    const api = asProvider({
      'GET /freelancers/me': () => json(200, makeProfile()),
      'PUT /freelancers/me': () =>
        json(200, makeProfile({ rate_per_hour: 45.5, rate_currency: 'AED' })),
    })
    renderApp('/member/profile')

    const name = await screen.findByLabelText('Full name')
    expect(name).toHaveValue('Fatima Khan')
    expect(screen.getByLabelText('Nationality')).toHaveValue('Indian')

    await ui.type(screen.getByLabelText('Rate per hour'), '45.5')
    await ui.type(screen.getByLabelText('Currency'), 'aed')
    await ui.click(screen.getByLabelText('The rate is negotiable'))
    await ui.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last('PUT /freelancers/me')?.body).toEqual({
      full_name: 'Fatima Khan',
      mobile_number: '+971500000001',
      whatsapp_availability: false,
      nationality: 'Indian',
      primary_language: null,
      rate_per_hour: 45.5,
      rate_currency: 'AED',
      is_rate_negotiable: true,
    })
  })

  it('wants the rate and the currency together', async () => {
    const ui = user()
    const api = asProvider({ 'GET /freelancers/me': () => json(200, makeProfile()) })
    renderApp('/member/profile')
    await ui.type(await screen.findByLabelText('Rate per hour'), '30')
    await ui.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/Give both the hourly rate and the currency/)).toBeVisible()
    expect(api.count('PUT /freelancers/me')).toBe(0)
  })

  it('rejects a currency that is not three letters', async () => {
    const ui = user()
    asProvider({ 'GET /freelancers/me': () => json(200, makeProfile()) })
    renderApp('/member/profile')
    await ui.type(await screen.findByLabelText('Rate per hour'), '30')
    await ui.type(screen.getByLabelText('Currency'), 'A1')
    await ui.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Use a 3-letter currency code such as AED.')).toBeVisible()
  })

  it('offers a retry when the profile cannot be loaded', async () => {
    const ui = user()
    let healthy = false
    asProvider({
      'GET /freelancers/me': () =>
        healthy ? json(200, makeProfile()) : apiError(503, 'service_unavailable'),
    })
    renderApp('/member/profile')
    expect(await screen.findByRole('alert')).toHaveTextContent(/temporarily unavailable/)
    healthy = true
    await ui.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByLabelText('Full name')).toHaveValue('Fatima Khan')
  })
})

describe('skills and labels page', () => {
  const routes = () => ({
    'GET /freelancers/me': () =>
      json(
        200,
        makeProfile({
          labels: [
            { label: PLUMBING, level: HALF },
            // Switched off by an admin since: it is not in the active list any more.
            { label: label('old', 'retired skill', 'skill'), level: null },
          ],
        }),
      ),
    'GET /labels': () => json(200, ALL_LABELS),
    'PUT /freelancers/me/labels': () => json(200, []),
  })

  it('starts from the current selection and saves the whole set', async () => {
    const ui = user()
    const api = asProvider(routes())
    renderApp('/member/skills')

    const plumbing = await screen.findByLabelText('plumbing')
    expect(plumbing).toBeChecked()
    expect(screen.getByLabelText('Level for plumbing')).toHaveValue('lv2')
    expect(screen.getByLabelText('carpentry')).not.toBeChecked()
    expect(screen.queryByLabelText('Level for carpentry')).not.toBeInTheDocument()

    await ui.click(screen.getByLabelText('carpentry'))
    await ui.selectOptions(screen.getByLabelText('Level for carpentry'), 'lv3')
    await ui.click(screen.getByLabelText('English'))
    await ui.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    const sent = (api.last('PUT /freelancers/me/labels')?.body as { labels: unknown[] }).labels
    expect(sent).toHaveLength(3) // the retired skill is not sent back
    expect(sent).toEqual(
      expect.arrayContaining([
        { label_id: PLUMBING.id, level_label_id: HALF.id },
        { label_id: CARPENTRY.id, level_label_id: EIGHTY.id },
        { label_id: ENGLISH.id, level_label_id: null },
      ]),
    )
  })

  it('removes a label and its level when it is unticked', async () => {
    const ui = user()
    const api = asProvider(routes())
    renderApp('/member/skills')
    await ui.click(await screen.findByLabelText('plumbing'))
    expect(screen.queryByLabelText('Level for plumbing')).not.toBeInTheDocument()
    await ui.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByRole('status')
    expect(api.last('PUT /freelancers/me/labels')?.body).toEqual({ labels: [] })
  })

  it('orders levels: words first, then by number', () => {
    expect(sortLevels([EIGHTY, BASIC, HALF]).map((level) => level.label_name)).toEqual([
      'basic',
      '50%',
      '80%',
    ])
  })

  it('shows a message for a kind with no labels', async () => {
    asProvider({
      'GET /freelancers/me': () => json(200, makeProfile()),
      'GET /labels': () => json(200, [PLUMBING]),
    })
    renderApp('/member/skills')
    expect((await screen.findAllByText('No labels of this kind are available yet.')).length).toBe(3)
  })
})

describe('availability page', () => {
  const FROM = '2026-12-01T09:00'
  const TO = '2026-12-03T18:00'
  const existing = {
    id: 'u1',
    unavailable_from: new Date('2026-12-10T08:00').toISOString(),
    unavailable_to: new Date('2026-12-12T20:00').toISOString(),
  }

  it('says so when there are no periods', async () => {
    asProvider({ 'GET /freelancers/me/unavailability': () => json(200, []) })
    renderApp('/member/availability')
    expect(await screen.findByText(/You have no unavailable periods/)).toBeVisible()
  })

  it('adds a period, sending UTC times, and clears the form', async () => {
    const ui = user()
    const api = asProvider({
      'GET /freelancers/me/unavailability': () => json(200, []),
      'POST /freelancers/me/unavailability': () => json(201, { ...existing, id: 'new' }),
    })
    renderApp('/member/availability')
    const from = await screen.findByLabelText('From')
    fireEvent.change(from, { target: { value: FROM } })
    fireEvent.change(screen.getByLabelText('Until'), { target: { value: TO } })
    await ui.click(screen.getByRole('button', { name: 'Add period' }))

    await waitFor(() => expect(from).toHaveValue(''))
    expect(api.last('POST /freelancers/me/unavailability')?.body).toEqual({
      unavailable_from: new Date(FROM).toISOString(),
      unavailable_to: new Date(TO).toISOString(),
    })
  })

  it('checks the dates before calling the API', async () => {
    const ui = user()
    const api = asProvider({
      'GET /freelancers/me/unavailability': () => json(200, []),
    })
    renderApp('/member/availability')
    await ui.click(await screen.findByRole('button', { name: 'Add period' }))
    expect(await screen.findAllByText('Choose a date and time.')).toHaveLength(2)

    fireEvent.change(screen.getByLabelText('From'), { target: { value: TO } })
    fireEvent.change(screen.getByLabelText('Until'), { target: { value: FROM } })
    await ui.click(screen.getByRole('button', { name: 'Add period' }))
    expect(await screen.findByText('The end must be after the start.')).toBeVisible()
    expect(api.count('POST /freelancers/me/unavailability')).toBe(0)
  })

  it('explains an overlap reported by the server', async () => {
    const ui = user()
    asProvider({
      'GET /freelancers/me/unavailability': () => json(200, [existing]),
      'POST /freelancers/me/unavailability': () => apiError(409, 'unavailability_overlaps'),
    })
    renderApp('/member/availability')
    fireEvent.change(await screen.findByLabelText('From'), { target: { value: FROM } })
    fireEvent.change(screen.getByLabelText('Until'), { target: { value: TO } })
    await ui.click(screen.getByRole('button', { name: 'Add period' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('overlaps one you already have')
  })

  it('edits a period, starting from its current values', async () => {
    const ui = user()
    const api = asProvider({
      'GET /freelancers/me/unavailability': () => json(200, [existing]),
      'PUT /freelancers/me/unavailability/u1': () => json(200, existing),
    })
    renderApp('/member/availability')
    await ui.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(screen.getByRole('heading', { name: 'Change period' })).toBeVisible()
    expect(screen.getByLabelText('From')).toHaveValue('2026-12-10T08:00')

    fireEvent.change(screen.getByLabelText('Until'), { target: { value: '2026-12-13T20:00' } })
    await ui.click(screen.getByRole('button', { name: 'Save changes' }))
    await screen.findByRole('heading', { name: 'Add a period' })
    expect(api.last('PUT /freelancers/me/unavailability/u1')?.body).toEqual({
      unavailable_from: existing.unavailable_from,
      unavailable_to: new Date('2026-12-13T20:00').toISOString(),
    })
  })

  it('asks for confirmation before deleting', async () => {
    const ui = user()
    const api = asProvider({
      'GET /freelancers/me/unavailability': () => json(200, [existing]),
      'DELETE /freelancers/me/unavailability/u1': () => json(204),
    })
    renderApp('/member/availability')
    await ui.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(api.count('DELETE /freelancers/me/unavailability/u1')).toBe(0)

    await ui.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Delete' })).toBeVisible()

    await ui.click(screen.getByRole('button', { name: 'Delete' }))
    await ui.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => expect(api.count('DELETE /freelancers/me/unavailability/u1')).toBe(1))
  })

  it('marks unavailable days on the calendar', async () => {
    const now = new Date()
    const period = {
      id: 'u9',
      unavailable_from: new Date(now.getFullYear(), now.getMonth(), 10, 8).toISOString(),
      unavailable_to: new Date(now.getFullYear(), now.getMonth(), 12, 8).toISOString(),
    }
    asProvider({ 'GET /freelancers/me/unavailability': () => json(200, [period]) })
    renderApp('/member/availability')
    const calendar = await screen.findByRole('region', { name: 'Calendar' })
    const marked = calendar.querySelectorAll('td.is-off')
    expect([...marked].map((cell) => cell.textContent?.trim())).toEqual([
      '10 unavailable',
      '11 unavailable',
      '12 unavailable',
    ])
  })
})

describe('ratings page', () => {
  const rows = (count: number, start = 0) =>
    Array.from({ length: count }, (_, index) => ({
      rating: ((start + index) % 10) + 1,
      comment: index === 0 ? 'Very reliable' : null,
      rated_on: `2026-10-${String(10 + index).padStart(2, '0')}T10:00:00Z`,
    }))

  it('says so when there are no ratings', async () => {
    asProvider({
      [`GET /freelancers/${ME_ID}/ratings?page=1&page_size=10`]: () =>
        json(200, { items: [], total: 0, page: 1, page_size: 10 }),
    })
    renderApp('/member/ratings')
    expect(await screen.findByText('You have not been rated yet.')).toBeVisible()
  })

  it('shows ratings and moves between pages', async () => {
    const ui = user()
    const api = asProvider({
      [`GET /freelancers/${ME_ID}/ratings?page=1&page_size=10`]: () =>
        json(200, { items: rows(10), total: 12, page: 1, page_size: 10 }),
      [`GET /freelancers/${ME_ID}/ratings?page=2&page_size=10`]: () =>
        json(200, { items: rows(2, 10), total: 12, page: 2, page_size: 10 }),
    })
    renderApp('/member/ratings')
    expect(await screen.findByText('12 rating(s)')).toBeVisible()
    expect(screen.getByText('Very reliable')).toBeVisible()
    expect(screen.getByText('Page 1 of 2')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await ui.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('Page 2 of 2')).toBeVisible()
    expect(api.count(`GET /freelancers/${ME_ID}/ratings?page=2&page_size=10`)).toBe(1)
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })
})
