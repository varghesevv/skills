import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { json, makePerson, renderApp, signedInAs } from '../../../testUtils'
import { ALL_LABELS } from '../provider/testData'
import { makeResult, page } from './testData'

// This test has a file of its own on purpose: it must be the first render of the search page in a
// fresh test environment. Only then does React run its effects a little after the page appears,
// as it does on a slow machine, which is when a keystroke could be lost.

const NAMED = 'GET /search/freelancers?name=anita&page=1&page_size=12'

/** The "Search by name" box, reported the moment it is added to the page. */
function nameBoxAppears(): Promise<HTMLInputElement> {
  return new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      const input = screen.queryByLabelText<HTMLInputElement>('Search by name')
      if (input) {
        observer.disconnect()
        resolve(input)
      }
    })
    observer.observe(document.body, { childList: true, subtree: true })
  })
}

describe('the name box of the search page', () => {
  it('keeps every letter typed as soon as the page appears', async () => {
    const api = signedInAs(undefined, {
      'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
      'GET /me': () => json(200, makePerson({ status: 'searcher' })),
      'GET /labels': () => json(200, ALL_LABELS),
      'GET /churches': () => json(200, { items: [] }),
      'GET /search/freelancers?page=1&page_size=12': () => json(200, page([makeResult()])),
      [NAMED]: () => json(200, page([makeResult()])),
    })
    const box = nameBoxAppears()
    renderApp('/member/search')
    const user = userEvent.setup({ delay: null })

    await user.type(await box, 'anita')
    expect(screen.getByLabelText('Search by name')).toHaveValue('anita')

    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('1 freelancer(s) found')).toBeVisible()
    expect(api.count(NAMED)).toBe(1)
  })
})
