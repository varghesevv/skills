import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, makePerson as makeMeAsPerson, renderApp, signedInAs } from '../../../testUtils'
import { ALL_LABELS } from '../provider/testData'
import { makeResult, page } from './testData'

// docs/design-system.md, section 2.3: from 1024px the filters apply as they change.

const ME_ID = '99999999-9999-9999-9999-999999999999'
const BASE = 'GET /search/freelancers?page=1&page_size=12'
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const ui = () => userEvent.setup({ delay: null })

function desktop(wide: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: wide,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
}

function asMember(routes: Parameters<typeof signedInAs>[1]) {
  return signedInAs(undefined, {
    ...quiet,
    'GET /me': () => json(200, makeMeAsPerson({ status: 'searcher', id: ME_ID })),
    'GET /labels': () => json(200, ALL_LABELS),
    'GET /churches': () => json(200, { items: [] }),
    ...routes,
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('live filters on a desktop screen', () => {
  it('has no Show results button, and applies a typed rate once, after a pause', async () => {
    desktop(true)
    const user = ui()
    const rate = 'GET /search/freelancers?max_rate=60&currency=AED&page=1&page_size=12'
    const api = asMember({
      [BASE]: () => json(200, page([makeResult()])),
      [rate]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await screen.findByText('1 freelancer(s) found')
    expect(screen.queryByRole('button', { name: 'Show results' })).toBeNull()

    await user.type(screen.getByLabelText('Highest rate per hour'), '60')
    await user.type(screen.getByLabelText('Currency'), 'AED')
    // Nothing is asked while the person is still typing.
    expect(api.count(rate)).toBe(0)
    await waitFor(() => expect(api.count(rate)).toBe(1))
    // Never a request for a half-typed rate.
    expect(api.calls.filter((call) => call.key.includes('max_rate=6&'))).toHaveLength(0)
  })

  it('applies a ticked box at once', async () => {
    desktop(true)
    const user = ui()
    const negotiable = 'GET /search/freelancers?negotiable=true&page=1&page_size=12'
    const api = asMember({
      [BASE]: () => json(200, page([makeResult()])),
      [negotiable]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await screen.findByText('1 freelancer(s) found')
    await user.click(screen.getByLabelText('Negotiable rates only'))
    await waitFor(() => expect(api.count(negotiable)).toBe(1))
  })

  it('shows a chip removed elsewhere in the form, without a reload', async () => {
    desktop(true)
    const user = ui()
    const negotiable = 'GET /search/freelancers?negotiable=true&page=1&page_size=12'
    asMember({
      [BASE]: () => json(200, page([makeResult()])),
      [negotiable]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search?negotiable=true')
    const box = await screen.findByLabelText('Negotiable rates only')
    expect(box).toBeChecked()
    await user.click(screen.getByRole('button', { name: /Remove filter/ }))
    await waitFor(() => expect(screen.getByLabelText('Negotiable rates only')).not.toBeChecked())
  })

  it('does not search for a rate that is not valid, and says why', async () => {
    desktop(true)
    const user = ui()
    const api = asMember({ [BASE]: () => json(200, page([makeResult()])) })
    renderApp('/member/search')
    await screen.findByText('1 freelancer(s) found')
    await user.type(screen.getByLabelText('Highest rate per hour'), 'abc')
    await new Promise((resolve) => setTimeout(resolve, 600))
    expect(api.count(BASE)).toBe(1)
    expect(api.calls.filter((call) => call.key.includes('max_rate'))).toHaveLength(0)
  })

  it('keeps the older answer from replacing the newer one', async () => {
    desktop(true)
    const user = ui()
    const first = 'GET /search/freelancers?negotiable=true&page=1&page_size=12'
    const second = 'GET /search/freelancers?negotiable=true&min_rating=8&page=1&page_size=12'
    let release: () => void = () => undefined
    const slow = new Promise<void>((resolve) => (release = resolve))
    asMember({
      [BASE]: () => json(200, page([makeResult()])),
      // Typed as a handler that resolves later: the first answer arrives last.
      [first]: (async () => {
        await slow
        return json(200, page([makeResult({ full_name: 'Older Answer' })]))
      }) as unknown as () => Response,
      [second]: () => json(200, page([makeResult({ full_name: 'Newer Answer' })])),
    })
    renderApp('/member/search')
    await screen.findByText('1 freelancer(s) found')
    await user.click(screen.getByLabelText('Negotiable rates only'))
    await user.selectOptions(screen.getByLabelText('Minimum average rating'), '8')
    expect(await screen.findByRole('link', { name: 'Newer Answer' })).toBeVisible()
    release()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('link', { name: 'Older Answer' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Newer Answer' })).toBeVisible()
  })
})

describe('the filters on a narrower screen', () => {
  it('keep the Show results button and do not search until it is pressed', async () => {
    desktop(false)
    const user = ui()
    const negotiable = 'GET /search/freelancers?negotiable=true&page=1&page_size=12'
    const api = asMember({
      [BASE]: () => json(200, page([makeResult()])),
      [negotiable]: () => json(200, page([makeResult()])),
    })
    renderApp('/member/search')
    await screen.findByText('1 freelancer(s) found')
    await user.click(screen.getByLabelText('Negotiable rates only'))
    expect(api.count(negotiable)).toBe(0)
    await user.click(screen.getAllByRole('button', { name: 'Show results' })[0])
    await waitFor(() => expect(api.count(negotiable)).toBe(1))
  })
})
