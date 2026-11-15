import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { json, makeMe, makePerson, renderApp, signedInAs } from '../../testUtils'

const build = {
  platform: 'android',
  version: '1.2.0',
  build: 7,
  released_at: '2026-11-10T08:00:00Z',
  size_bytes: 5 * 1024 * 1024,
  sha256: 'a'.repeat(64),
  notes: 'Faster search',
  filename: 'skills-demo-1.2.0.apk',
}
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const as = (status: string, routes: Record<string, () => Response> = {}) =>
  signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () => json(200, makePerson({ status: status as 'provider' })),
    ...routes,
  })

afterEach(() => vi.restoreAllMocks())

describe('the Android app page', () => {
  it.each(['pending', 'searcher', 'owner'])(
    'is linked from the top bar of a %s',
    async (status) => {
      as(status)
      renderApp('/member')
      const link = await screen.findByRole('link', { name: 'Android app' })
      expect(link).toHaveAttribute('href', '/member/downloads')
    },
  )

  it('lists the builds with their size and checksum', async () => {
    as('searcher', { 'GET /app/downloads': () => json(200, { items: [build] }) })
    renderApp('/member/downloads')
    expect(await screen.findByText('Version 1.2.0 (build 7)')).toBeVisible()
    expect(screen.getByText('Faster search')).toBeVisible()
    expect(screen.getByText('a'.repeat(64))).toBeVisible()
    expect(screen.getByText(/5\.0 MB/)).toBeVisible()
  })

  it('says so when nothing is published', async () => {
    as('searcher', { 'GET /app/downloads': () => json(200, { items: [] }) })
    renderApp('/member/downloads')
    expect(await screen.findByText('No build has been published yet.')).toBeVisible()
  })

  it('fetches the file with the token and hands it to the browser', async () => {
    const urls: string[] = []
    as('provider', {
      'GET /app/downloads': () => json(200, { items: [build] }),
      'GET /app/downloads/android/1.2.0': () => {
        urls.push('file')
        return new Response('apk-bytes', {
          headers: { 'Content-Disposition': 'attachment; filename="skills-demo-1.2.0.apk"' },
        })
      },
    })
    const create = vi.fn(() => 'blob:x')
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderApp('/member/downloads')
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: 'Download version 1.2.0' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(urls).toEqual(['file'])
    expect(create).toHaveBeenCalled()
  })

  it('is closed to a revoked person, who is sent home', async () => {
    as('revoked')
    renderApp('/member/downloads')
    expect(await screen.findByRole('heading', { name: /no access/i })).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Android app' })).toBeNull()
  })
})
