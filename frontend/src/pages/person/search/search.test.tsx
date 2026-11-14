import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import {
  apiError,
  json,
  makePerson as makeMeAsPerson,
  renderApp,
  signedInAs,
} from '../../../testUtils'
import { ALL_LABELS, label } from '../../../portals/freelancer/testData'
import { PERSON_ID, makePerson, makeResult, page } from './testData'

const ui = () => userEvent.setup({ delay: null })
const ME_ID = '99999999-9999-9999-9999-999999999999'
const LABELS = [...ALL_LABELS, label('nt1', 'Indian', 'nativity')]
const DEFAULT_SEARCH = 'GET /search/freelancers?page=1&page_size=12'
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}

/** A SEARCHER (or another status) looking at providers. */
function asMember(routes: Parameters<typeof signedInAs>[1] = {}, status: string = 'searcher') {
  return signedInAs(undefined, {
    ...quiet,
    'GET /me': () => json(200, makeMeAsPerson({ status: status as 'searcher', id: ME_ID })),
    'GET /labels': () => json(200, LABELS),
    'GET /churches': () => json(200, { items: [] }),
    ...routes,
  })
}

describe('search', () => {
  it('lists freelancers with rate, rating and skills', async () => {
    asMember({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/member/search')
    const link = await screen.findByRole('link', { name: 'Anita Sharma' })
    expect(link).toHaveAttribute('href', `/member/providers/${PERSON_ID}`)
    expect(screen.getByText('50 AED per hour')).toBeVisible()
    expect(screen.getByText('Negotiable')).toBeVisible()
    expect(screen.getByText(/8\.5 out of 10 \(4\)/)).toBeVisible()
    expect(screen.getByText(/Grace Church · Riverside/)).toBeVisible()
    expect(within(link.closest('li')!).getByText('plumbing')).toBeVisible()
    expect(screen.getByText('1 freelancer(s) found')).toBeVisible()
  })

  it('says so when nothing matches', async () => {
    asMember({ [DEFAULT_SEARCH]: () => json(200, page([])) })
    renderApp('/member/search')
    expect(await screen.findByText('No freelancer matches. Try fewer filters.')).toBeVisible()
  })

  it('sends the chosen filters to the API and keeps them in the address', async () => {
    const user = ui()
    const filtered =
      'GET /search/freelancers?skill=plumbing&max_rate=60&currency=AED&page=1&page_size=12'
    const api = asMember({
      [DEFAULT_SEARCH]: () =>
        json(200, page([makeResult(), makeResult({ id: 'x', full_name: 'B' })])),
      [filtered]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await user.click(await screen.findByLabelText('plumbing'))
    await user.type(screen.getByLabelText('Highest rate per hour'), '60')
    await user.type(screen.getByLabelText('Currency'), 'aed')
    await user.click(screen.getAllByRole('button', { name: 'Show results' })[0])

    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(filtered)).toBe(1)
    expect(screen.getByRole('button', { name: 'Filters (2)' })).toBeVisible()
  })

  it('searches by name and shows the name as a removable filter', async () => {
    const user = ui()
    const named = 'GET /search/freelancers?name=anita&page=1&page_size=12'
    const api = asMember({
      [DEFAULT_SEARCH]: () => json(200, page([makeResult(), makeResult({ id: 'x' })])),
      [named]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await user.type(await screen.findByLabelText('Search by name'), 'anita')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(named)).toBe(1)

    await user.click(screen.getByRole('button', { name: 'Remove filter: Name: anita' }))
    await waitFor(() => expect(screen.getByLabelText('Search by name')).toHaveValue(''))
    expect(screen.queryByRole('list', { name: 'Active filters' })).not.toBeInTheDocument()
  })

  it('removes one filter from its chip and offers to clear everything when nothing matches', async () => {
    const user = ui()
    const both = 'GET /search/freelancers?skill=plumbing&language=English&page=1&page_size=12'
    const oneLeft = 'GET /search/freelancers?skill=plumbing&page=1&page_size=12'
    const api = asMember({
      [both]: () => json(200, page([])),
      [oneLeft]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search?skill=plumbing&language=English')
    expect(await screen.findByText('No freelancer matches. Try fewer filters.')).toBeVisible()
    // One next to the filter chips and one in the empty message.
    expect(screen.getAllByRole('button', { name: 'Clear all filters' })).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: 'Remove filter: English' }))
    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(oneLeft)).toBe(1)
  })

  it('filters by the church and its home group', async () => {
    const user = ui()
    const byChurch = 'GET /search/freelancers?church_id=church-2&page=1&page_size=12'
    const byGroup =
      'GET /search/freelancers?church_id=church-2&home_group_id=group-9&page=1&page_size=12'
    const api = asMember({
      'GET /churches': () =>
        json(200, {
          items: [
            { id: 'church-1', name: 'Grace Church' },
            { id: 'church-2', name: 'Hope Church' },
          ],
        }),
      'GET /churches/church-2/home-groups': () =>
        json(200, { items: [{ id: 'group-9', name: 'Harbour', leader_name: 'Hal' }] }),
      [DEFAULT_SEARCH]: () => json(200, page([makeResult(), makeResult({ id: 'x' })])),
      [byChurch]: () => json(200, page([makeResult()])),
      [byGroup]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await user.selectOptions(await screen.findByLabelText('Organisation'), 'Hope Church')
    await user.selectOptions(await screen.findByLabelText('Home group'), 'Harbour')
    await user.click(screen.getAllByRole('button', { name: 'Show results' })[0])
    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(byGroup)).toBe(1)
    expect(screen.getByRole('button', { name: 'Remove filter: Hope Church' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Remove filter: Harbour' })).toBeVisible()
  })

  it('explains a missing currency instead of calling the API', async () => {
    const user = ui()
    const api = asMember({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/member/search')
    await user.type(await screen.findByLabelText('Highest rate per hour'), '60')
    await user.click(screen.getAllByRole('button', { name: 'Show results' })[0])
    expect(await screen.findByText('Add the currency for this rate.')).toBeVisible()
    expect(api.calls.filter((call) => call.key.includes('max_rate'))).toHaveLength(0)
  })

  it('starts from the filters in the address, and clears them', async () => {
    const user = ui()
    const key = 'GET /search/freelancers?skill=plumbing&sort=rate&page=1&page_size=12'
    const cleared = 'GET /search/freelancers?sort=rate&page=1&page_size=12'
    const api = asMember({
      [key]: () => json(200, page([makeResult()])),
      [cleared]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search?skill=plumbing&sort=rate')
    expect(await screen.findByLabelText('plumbing')).toBeChecked()
    expect(screen.getByLabelText('Sort by')).toHaveValue('rate')
    expect(api.count(key)).toBe(1)

    await user.click(screen.getAllByRole('button', { name: 'Clear filters' })[0])
    await waitFor(() => expect(api.count(cleared)).toBe(1))
    expect(screen.getByLabelText('plumbing')).not.toBeChecked()
  })

  it('changes the sort order', async () => {
    const user = ui()
    const sorted = 'GET /search/freelancers?sort=rating&page=1&page_size=12'
    const api = asMember({
      [DEFAULT_SEARCH]: () => json(200, page([makeResult()])),
      [sorted]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await user.selectOptions(await screen.findByLabelText('Sort by'), 'rating')
    await waitFor(() => expect(api.count(sorted)).toBe(1))
  })

  it('moves between pages', async () => {
    const user = ui()
    const second = 'GET /search/freelancers?page=2&page_size=12'
    const api = asMember({
      [DEFAULT_SEARCH]: () => json(200, page([makeResult()], 30)),
      [second]: () => json(200, page([makeResult({ full_name: 'Second Page' })], 30, 2)),
    })
    renderApp('/member/search')
    expect(await screen.findByText('Page 1 of 3')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('link', { name: 'Second Page' })).toBeVisible()
    expect(api.count(second)).toBe(1)
  })

  it('opens and closes the filter panel on small screens', async () => {
    const user = ui()
    asMember({ [DEFAULT_SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/member/search')
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
    asMember({
      [key]: () => json(200, page([makeResult()])),
      [`GET /freelancers/${PERSON_ID}`]: () => json(200, makePerson()),
      [`GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`]: () =>
        json(200, { items: [], total: 0, page: 1, page_size: 10 }),
    })
    renderApp('/member/search?skill=plumbing')
    await user.click(await screen.findByRole('link', { name: 'Anita Sharma' }))
    const back = await screen.findByRole('link', { name: /Back to search/ })
    expect(back).toHaveAttribute('href', '/member/search?skill=plumbing')
  })
})

describe('freelancer detail', () => {
  const ratings = `GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`
  const emptyRatings = () => json(200, { items: [], total: 0, page: 1, page_size: 10 })
  const detail = `GET /freelancers/${PERSON_ID}`

  it('shows what a member needs to decide', async () => {
    asMember({ [detail]: () => json(200, makePerson()), [ratings]: emptyRatings })
    renderApp(`/member/providers/${PERSON_ID}`)
    expect(await screen.findByRole('heading', { name: 'Anita Sharma' })).toBeVisible()
    expect(screen.queryByText('+971500000011')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reveal the mobile number/ })).toBeVisible()
    expect(screen.getByText('50 AED per hour')).toBeVisible()
    expect(screen.getByText(/Grace Church · Riverside/)).toBeVisible()
    expect(screen.getByText('plumbing')).toBeVisible()
    expect(screen.getByText('English')).toBeVisible()
    expect(screen.getByText(/Dec/)).toBeVisible()
  })

  it('creates a rating, then offers to change it', async () => {
    const user = ui()
    let mine: ReturnType<typeof makePerson>['my_rating'] = null
    const given = {
      id: 'r1',
      provider_id: PERSON_ID,
      provider_name: 'Anita Sharma',
      rating: 9,
      comment: 'Excellent',
      rated_on: '2026-10-20T10:00:00Z',
      updated_at: null,
    }
    const api = asMember({
      [detail]: () => json(200, makePerson({ my_rating: mine })),
      [ratings]: emptyRatings,
      'POST /ratings': () => {
        mine = given
        return json(201, given)
      },
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    await screen.findByRole('heading', { name: 'Rate this freelancer' })
    await user.selectOptions(screen.getByLabelText('Score (1 to 10)'), '9')
    await user.type(screen.getByLabelText('Comment (optional)'), 'Excellent')
    await user.click(screen.getByRole('button', { name: 'Save rating' }))

    expect(await screen.findByRole('heading', { name: 'Change your rating' })).toBeVisible()
    expect(api.last('POST /ratings')?.body).toEqual({
      provider_id: PERSON_ID,
      rating: 9,
      comment: 'Excellent',
    })
    expect(screen.getByText('Your rating was saved.')).toBeVisible()
  })

  it('updates an existing rating', async () => {
    const user = ui()
    const mine = {
      id: 'r1',
      provider_id: PERSON_ID,
      provider_name: 'Anita Sharma',
      rating: 6,
      comment: null,
      rated_on: '2026-10-20T10:00:00Z',
      updated_at: null,
    }
    const api = asMember({
      [detail]: () => json(200, makePerson({ my_rating: mine })),
      [ratings]: emptyRatings,
      'PUT /ratings/r1': () => json(200, { ...mine, rating: 10 }),
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    const score = await screen.findByLabelText('Score (1 to 10)')
    expect(score).toHaveValue('6')
    await user.selectOptions(score, '10')
    await user.click(screen.getByRole('button', { name: 'Update rating' }))
    await waitFor(() => expect(api.count('PUT /ratings/r1')).toBe(1))
    expect(api.last('PUT /ratings/r1')?.body).toEqual({ rating: 10, comment: null })
  })

  it('asks for a score before calling the API', async () => {
    const user = ui()
    const api = asMember({ [detail]: () => json(200, makePerson()), [ratings]: emptyRatings })
    renderApp(`/member/providers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Save rating' }))
    expect(await screen.findByText('Choose a score from 1 to 10.')).toBeVisible()
    expect(api.count('POST /ratings')).toBe(0)
  })

  it('explains when the freelancer was already rated', async () => {
    const user = ui()
    asMember({
      [detail]: () => json(200, makePerson()),
      [ratings]: emptyRatings,
      'POST /ratings': () => apiError(409, 'already_rated'),
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    await user.selectOptions(await screen.findByLabelText('Score (1 to 10)'), '5')
    await user.click(screen.getByRole('button', { name: 'Save rating' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already rated')
  })

  it('shows an error with a retry when the freelancer cannot be found', async () => {
    asMember({ [detail]: () => apiError(404, 'not_found') })
    renderApp(`/member/providers/${PERSON_ID}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('no longer exists')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible()
  })
})

describe('ratings I gave', () => {
  const item = (id: string, name: string | null) => ({
    id,
    provider_id: PERSON_ID,
    provider_name: name,
    rating: 7,
    comment: 'Good work',
    rated_on: '2026-10-20T10:00:00Z',
    updated_at: '2026-10-21T10:00:00Z',
  })

  it('lists ratings with the freelancer name and a link to change them', async () => {
    asMember({
      'GET /workhosts/me/ratings?page=1&page_size=10': () =>
        json(200, page([item('r1', 'Anita Sharma'), item('r2', null)], 2)),
    })
    renderApp('/member/ratings-given')
    const link = await screen.findByRole('link', { name: 'Anita Sharma' })
    expect(link).toHaveAttribute('href', `/member/providers/${PERSON_ID}`)
    expect(screen.getByRole('link', { name: 'Unnamed freelancer' })).toBeVisible()
    expect(screen.getAllByText('Good work')).toHaveLength(2)
    expect(screen.getAllByText(/Updated/).length).toBeGreaterThan(0)
  })

  it('says so when nothing was rated', async () => {
    asMember({ 'GET /workhosts/me/ratings?page=1&page_size=10': () => json(200, page([])) })
    renderApp('/member/ratings-given')
    expect(await screen.findByText('You have not rated anyone yet.')).toBeVisible()
  })
})

describe('mobile number reveal', () => {
  const NUMBER = '+971500000011'
  const reveal = `POST /freelancers/${PERSON_ID}/reveal-mobile`
  const detail = `GET /freelancers/${PERSON_ID}`
  const ratings = `GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`
  const emptyRatings = () => json(200, { items: [], total: 0, page: 1, page_size: 10 })

  function phone() {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: true, media: query }))
  }

  it('hides the number in search results until Reveal is pressed', async () => {
    const user = ui()
    const api = asMember({
      'GET /search/freelancers?skill=plumbing&page=1&page_size=12': () =>
        json(200, page([makeResult()])),
      [reveal]: () => json(200, { mobile_number: NUMBER }),
    })
    renderApp('/member/search?skill=plumbing')
    const button = await screen.findByRole('button', {
      name: 'Reveal the mobile number of Anita Sharma',
    })
    expect(screen.queryByText(NUMBER)).not.toBeInTheDocument()
    expect(screen.getByText('Mobile number hidden')).toBeInTheDocument()
    expect(api.count(reveal)).toBe(0)

    await user.click(button)

    expect(await screen.findByRole('link', { name: `Call ${NUMBER}` })).toHaveAttribute(
      'href',
      `tel:${NUMBER}`,
    )
    expect(api.last(reveal)?.body).toEqual({
      channel: 'show',
      source: 'search',
      searched_skills: ['plumbing'],
    })
    expect(screen.queryByRole('button', { name: /Reveal/ })).not.toBeInTheDocument()
  })

  it('opens the dialler on a phone', async () => {
    phone()
    const user = ui()
    const dialled: string[] = []
    const onClick = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest('a')
      if (link?.getAttribute('href')?.startsWith('tel:')) {
        event.preventDefault()
        dialled.push(link.getAttribute('href') ?? '')
      }
    }
    document.addEventListener('click', onClick)
    const api = asMember({
      [detail]: () => json(200, makePerson()),
      [ratings]: emptyRatings,
      [reveal]: () => json(200, { mobile_number: NUMBER }),
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: /Reveal the mobile number/ }))

    await waitFor(() => expect(dialled).toEqual([`tel:${NUMBER}`]))
    document.removeEventListener('click', onClick)
    expect(api.last(reveal)?.body).toEqual({
      channel: 'dial',
      source: 'detail',
      searched_skills: [],
    })
  })

  it('shows the number without dialling on a computer', async () => {
    const user = ui()
    asMember({
      [detail]: () => json(200, makePerson()),
      [ratings]: emptyRatings,
      [reveal]: () => json(200, { mobile_number: NUMBER }),
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: /Reveal the mobile number/ }))
    expect(await screen.findByText(NUMBER)).toBeVisible()
  })

  it('explains when the limit is reached and lets the host try again', async () => {
    const user = ui()
    asMember({
      [detail]: () => json(200, makePerson()),
      [ratings]: emptyRatings,
      [reveal]: () => apiError(429, 'reveal_limit_reached', {}, { 'Retry-After': '1800' }),
    })
    renderApp(`/member/providers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: /Reveal the mobile number/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 30 minute(s).')
    expect(screen.getByRole('button', { name: /Reveal the mobile number/ })).toBeEnabled()
    expect(screen.queryByText(NUMBER)).not.toBeInTheDocument()
  })

  it('is not offered for the searcher’s own profile', async () => {
    asMember(
      {
        [`GET /freelancers/${ME_ID}`]: () => json(200, makePerson({ id: ME_ID })),
        [`GET /freelancers/${ME_ID}/ratings?page=1&page_size=10`]: emptyRatings,
      },
      'provider',
    )
    renderApp(`/member/providers/${ME_ID}`)
    expect(await screen.findByRole('heading', { name: 'Anita Sharma' })).toBeVisible()
    expect(screen.queryByRole('button', { name: /Reveal/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save|Rate/ })).not.toBeInTheDocument()
  })
})

describe('who may search', () => {
  it.each(['searcher', 'provider', 'verifier', 'admin', 'owner'])(
    'shows the menu to a %s',
    async (status) => {
      asMember({}, status)
      renderApp('/member')
      const nav = await screen.findByRole('navigation', { name: 'Find freelancers' })
      expect(
        within(nav)
          .getAllByRole('link')
          .map((link) => link.textContent),
      ).toEqual(['Find freelancers', 'Ratings I gave'])
    },
  )

  it.each(['/member/search', `/member/providers/${PERSON_ID}`, '/member/ratings-given'])(
    'sends an applicant from %s to their home without a call',
    async (path) => {
      const api = asMember({}, 'pending')
      renderApp(path)
      expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
      expect(
        api.calls.some(
          (call) =>
            call.key.includes('/search/') ||
            call.key.includes('/freelancers/') ||
            call.key.includes('/workhosts/'),
        ),
      ).toBe(false)
      expect(screen.queryByRole('navigation', { name: 'Find freelancers' })).toBeNull()
    },
  )
})
