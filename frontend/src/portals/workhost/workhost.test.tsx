import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, renderApp, signedInAs } from '../../testUtils'
import { ALL_LABELS, label } from '../freelancer/testData'
import { PERSON_ID, makePerson, makeResult, page } from './testData'

const ui = () => userEvent.setup({ delay: null })
const host = makeMe({ user_type: 'workhost', full_name: 'Wael Host', email: 'w@example.com' })
const LABELS = [...ALL_LABELS, label('nt1', 'Indian', 'nativity')]
const DEFAULT_SEARCH = 'GET /search/freelancers?page=1&page_size=12'

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
    ).toEqual(['Dashboard', 'Find freelancers', 'Ratings I gave', 'Profile'])
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

describe('search', () => {
  it('lists freelancers with rate, rating and skills', async () => {
    asHost({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/workhost/search')
    const link = await screen.findByRole('link', { name: 'Anita Sharma' })
    expect(link).toHaveAttribute('href', `/workhost/freelancers/${PERSON_ID}`)
    expect(screen.getByText('50 AED per hour')).toBeVisible()
    expect(screen.getByText('Negotiable')).toBeVisible()
    expect(screen.getByText(/8\.5 out of 10 \(4\)/)).toBeVisible()
    expect(screen.getByText(/2 organisation\(s\) vouch/)).toBeVisible()
    expect(within(link.closest('li')!).getByText('plumbing')).toBeVisible()
    expect(screen.getByText('1 freelancer(s) found')).toBeVisible()
  })

  it('says so when nothing matches', async () => {
    asHost({ [DEFAULT_SEARCH]: () => json(200, page([])) })
    renderApp('/workhost/search')
    expect(await screen.findByText('No freelancer matches. Try fewer filters.')).toBeVisible()
  })

  it('sends the chosen filters to the API and keeps them in the address', async () => {
    const user = ui()
    const filtered =
      'GET /search/freelancers?skill=plumbing&max_rate=60&currency=AED&page=1&page_size=12'
    const api = asHost({
      [DEFAULT_SEARCH]: () =>
        json(200, page([makeResult(), makeResult({ id: 'x', full_name: 'B' })])),
      [filtered]: () => json(200, page([makeResult()])),
    })
    renderApp('/workhost/search')
    await user.click(await screen.findByLabelText('plumbing'))
    await user.type(screen.getByLabelText('Highest rate per hour'), '60')
    await user.type(screen.getByLabelText('Currency'), 'aed')
    await user.click(screen.getByRole('button', { name: 'Show results' }))

    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(filtered)).toBe(1)
    expect(screen.getByRole('button', { name: 'Filters (2)' })).toBeVisible()
  })

  it('filters by the organisation that vouches', async () => {
    const user = ui()
    const filtered = 'GET /search/freelancers?org_id=org-1&page=1&page_size=12'
    const api = asHost({
      'GET /organisations': () =>
        json(200, [
          { id: 'org-1', org_name: 'Acme Training' },
          { id: 'org-2', org_name: 'Beta Academy' },
        ]),
      [DEFAULT_SEARCH]: () => json(200, page([makeResult(), makeResult({ id: 'x' })])),
      [filtered]: () => json(200, page([makeResult()])),
    })
    renderApp('/workhost/search')
    await user.selectOptions(await screen.findByLabelText('Vouched by'), 'Acme Training')
    await user.click(screen.getByRole('button', { name: 'Show results' }))
    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(filtered)).toBe(1)
  })

  it('explains a missing currency instead of calling the API', async () => {
    const user = ui()
    const api = asHost({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/workhost/search')
    await user.type(await screen.findByLabelText('Highest rate per hour'), '60')
    await user.click(screen.getByRole('button', { name: 'Show results' }))
    expect(await screen.findByText('Add the currency for this rate.')).toBeVisible()
    expect(api.calls.filter((call) => call.key.includes('max_rate'))).toHaveLength(0)
  })

  it('starts from the filters in the address, and clears them', async () => {
    const user = ui()
    const key = 'GET /search/freelancers?skill=plumbing&sort=rate&page=1&page_size=12'
    const cleared = 'GET /search/freelancers?sort=rate&page=1&page_size=12'
    const api = asHost({
      [key]: () => json(200, page([makeResult()])),
      [cleared]: () => json(200, page([makeResult()])),
    })
    renderApp('/workhost/search?skill=plumbing&sort=rate')
    expect(await screen.findByLabelText('plumbing')).toBeChecked()
    expect(screen.getByLabelText('Sort by')).toHaveValue('rate')
    expect(api.count(key)).toBe(1)

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    await waitFor(() => expect(api.count(cleared)).toBe(1))
    expect(screen.getByLabelText('plumbing')).not.toBeChecked()
  })

  it('changes the sort order', async () => {
    const user = ui()
    const sorted = 'GET /search/freelancers?sort=rating&page=1&page_size=12'
    const api = asHost({
      [DEFAULT_SEARCH]: () => json(200, page([makeResult()])),
      [sorted]: () => json(200, page([makeResult()])),
    })
    renderApp('/workhost/search')
    await user.selectOptions(await screen.findByLabelText('Sort by'), 'rating')
    await waitFor(() => expect(api.count(sorted)).toBe(1))
  })

  it('moves between pages', async () => {
    const user = ui()
    const second = 'GET /search/freelancers?page=2&page_size=12'
    const api = asHost({
      [DEFAULT_SEARCH]: () => json(200, page([makeResult()], 30)),
      [second]: () => json(200, page([makeResult({ full_name: 'Second Page' })], 30, 2)),
    })
    renderApp('/workhost/search')
    expect(await screen.findByText('Page 1 of 3')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('link', { name: 'Second Page' })).toBeVisible()
    expect(api.count(second)).toBe(1)
  })

  it('opens and closes the filter panel on small screens', async () => {
    const user = ui()
    asHost({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/workhost/search')
    const toggle = await screen.findByRole('button', { name: 'Filters' })
    const panel = document.getElementById('filter-panel')!
    expect(panel).toHaveAttribute('data-open', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(panel).toHaveAttribute('data-open', 'true')
    await user.keyboard('{Escape}')
    expect(panel).toHaveAttribute('data-open', 'false')
    expect(toggle).toHaveFocus()
  })

  it('keeps the search when going to a profile and back', async () => {
    const user = ui()
    const key = 'GET /search/freelancers?skill=plumbing&page=1&page_size=12'
    asHost({
      [key]: () => json(200, page([makeResult()])),
      [`GET /freelancers/${PERSON_ID}`]: () => json(200, makePerson()),
      [`GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`]: () =>
        json(200, { items: [], total: 0, page: 1, page_size: 10 }),
    })
    renderApp('/workhost/search?skill=plumbing')
    await user.click(await screen.findByRole('link', { name: 'Anita Sharma' }))
    const back = await screen.findByRole('link', { name: /Back to search/ })
    expect(back).toHaveAttribute('href', '/workhost/search?skill=plumbing')
  })
})

describe('freelancer detail', () => {
  const ratings = `GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`
  const emptyRatings = () => json(200, { items: [], total: 0, page: 1, page_size: 10 })
  const detail = `GET /freelancers/${PERSON_ID}`

  it('shows what a work host needs to decide', async () => {
    asHost({ [detail]: () => json(200, makePerson()), [ratings]: emptyRatings })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    expect(await screen.findByRole('heading', { name: 'Anita Sharma' })).toBeVisible()
    expect(screen.getByRole('link', { name: '+971500000011' })).toHaveAttribute(
      'href',
      'tel:+971500000011',
    )
    expect(screen.getByText('50 AED per hour')).toBeVisible()
    expect(screen.getByText('Acme Training')).toBeVisible()
    expect(screen.getByText('plumbing')).toBeVisible()
    expect(screen.getByText('English')).toBeVisible()
    expect(screen.getByText(/Dec/)).toBeVisible()
  })

  it('creates a rating, then offers to change it', async () => {
    const user = ui()
    let mine: ReturnType<typeof makePerson>['my_rating'] = null
    const given = {
      id: 'r1',
      freelancer_id: PERSON_ID,
      freelancer_name: 'Anita Sharma',
      rating: 9,
      comment: 'Excellent',
      rated_on: '2026-10-20T10:00:00Z',
      updated_at: null,
    }
    const api = asHost({
      [detail]: () => json(200, makePerson({ my_rating: mine })),
      [ratings]: emptyRatings,
      'POST /ratings': () => {
        mine = given
        return json(201, given)
      },
    })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    await screen.findByRole('heading', { name: 'Rate this freelancer' })
    await user.selectOptions(screen.getByLabelText('Score (1 to 10)'), '9')
    await user.type(screen.getByLabelText('Comment (optional)'), 'Excellent')
    await user.click(screen.getByRole('button', { name: 'Save rating' }))

    expect(await screen.findByRole('heading', { name: 'Change your rating' })).toBeVisible()
    expect(api.last('POST /ratings')?.body).toEqual({
      freelancer_id: PERSON_ID,
      rating: 9,
      comment: 'Excellent',
    })
    expect(screen.getByText('Your rating was saved.')).toBeVisible()
  })

  it('updates an existing rating', async () => {
    const user = ui()
    const mine = {
      id: 'r1',
      freelancer_id: PERSON_ID,
      freelancer_name: 'Anita Sharma',
      rating: 6,
      comment: null,
      rated_on: '2026-10-20T10:00:00Z',
      updated_at: null,
    }
    const api = asHost({
      [detail]: () => json(200, makePerson({ my_rating: mine })),
      [ratings]: emptyRatings,
      'PUT /ratings/r1': () => json(200, { ...mine, rating: 10 }),
    })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    const score = await screen.findByLabelText('Score (1 to 10)')
    expect(score).toHaveValue('6')
    await user.selectOptions(score, '10')
    await user.click(screen.getByRole('button', { name: 'Update rating' }))
    await waitFor(() => expect(api.count('PUT /ratings/r1')).toBe(1))
    expect(api.last('PUT /ratings/r1')?.body).toEqual({ rating: 10, comment: null })
  })

  it('asks for a score before calling the API', async () => {
    const user = ui()
    const api = asHost({ [detail]: () => json(200, makePerson()), [ratings]: emptyRatings })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Save rating' }))
    expect(await screen.findByText('Choose a score from 1 to 10.')).toBeVisible()
    expect(api.count('POST /ratings')).toBe(0)
  })

  it('explains when the freelancer was already rated', async () => {
    const user = ui()
    asHost({
      [detail]: () => json(200, makePerson()),
      [ratings]: emptyRatings,
      'POST /ratings': () => apiError(409, 'already_rated'),
    })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    await user.selectOptions(await screen.findByLabelText('Score (1 to 10)'), '5')
    await user.click(screen.getByRole('button', { name: 'Save rating' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already rated')
  })

  it('shows an error with a retry when the freelancer cannot be found', async () => {
    asHost({ [detail]: () => apiError(404, 'not_found') })
    renderApp(`/workhost/freelancers/${PERSON_ID}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('no longer exists')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
  })
})

describe('ratings I gave', () => {
  const item = (id: string, name: string | null) => ({
    id,
    freelancer_id: PERSON_ID,
    freelancer_name: name,
    rating: 7,
    comment: 'Good work',
    rated_on: '2026-10-20T10:00:00Z',
    updated_at: '2026-10-21T10:00:00Z',
  })

  it('lists ratings with the freelancer name and a link to change them', async () => {
    asHost({
      'GET /workhosts/me/ratings?page=1&page_size=10': () =>
        json(200, page([item('r1', 'Anita Sharma'), item('r2', null)], 2)),
    })
    renderApp('/workhost/ratings')
    const link = await screen.findByRole('link', { name: 'Anita Sharma' })
    expect(link).toHaveAttribute('href', `/workhost/freelancers/${PERSON_ID}`)
    expect(screen.getByRole('link', { name: 'Unnamed freelancer' })).toBeVisible()
    expect(screen.getAllByText('Good work')).toHaveLength(2)
    expect(screen.getAllByText(/Updated/).length).toBeGreaterThan(0)
  })

  it('says so when nothing was rated', async () => {
    asHost({ 'GET /workhosts/me/ratings?page=1&page_size=10': () => json(200, page([])) })
    renderApp('/workhost/ratings')
    expect(await screen.findByText('You have not rated anyone yet.')).toBeVisible()
  })
})
