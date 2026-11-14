import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  apiError,
  json,
  makeMe,
  makePerson,
  mockApi,
  renderApp,
  signedInAs,
} from '../../../testUtils'

const GROUPS = 'GET /churches/church-1/home-groups'
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
const TWO = () =>
  json(200, {
    items: [
      { id: 'group-1', name: 'Riverside', leader_name: 'Lena Leader' },
      { id: 'g2', name: 'Harbour', leader_name: 'Hal Harbour' },
    ],
  })
const lead = (
  status = 'verifier',
  me = () =>
    makePerson({
      status: status as 'verifier',
      full_name: 'Lena Leader',
      leader: { name: 'Lena Leader' },
    }),
) => ({
  ...quiet,
  'GET /me': () => json(200, me()),
  [GROUPS]: TWO,
})
const CLOSED = {
  closed_group: { id: 'group-1', name: 'Riverside' },
  joined_group: { id: 'g2', name: 'Harbour' },
  status: 'provider',
}

describe('close my group', () => {
  it('asks first, then closes it into the chosen group, as a provider', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...lead(),
      'POST /home-groups/group-1/close': () => json(200, CLOSED),
    })
    renderApp('/member/group')
    await screen.findByRole('option', { name: 'Harbour' })
    expect(screen.queryByRole('option', { name: 'Riverside' })).toBeNull()
    const submit = screen.getByRole('button', { name: 'Close Riverside' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Join'), 'g2')
    await user.selectOptions(screen.getByLabelText('Afterwards I am'), 'searcher')
    await user.click(submit)
    expect(api.count('POST /home-groups/group-1/close')).toBe(0)
    expect(screen.getByText(/It cannot be undone/)).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(await screen.findByText('Riverside is closed. You joined Harbour.')).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /home-groups/group-1/close')?.body).toEqual({
      move_to_group_id: 'g2',
      former_leader_status: 'searcher',
    })
  })

  it('can be cancelled at the question', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), lead())
    renderApp('/member/group')
    await screen.findByRole('option', { name: 'Harbour' })
    await user.selectOptions(screen.getByLabelText('Join'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Close Riverside' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Close Riverside' })).toBeVisible()
    expect(api.count('POST /home-groups/group-1/close')).toBe(0)
  })

  it('keeps their status when they are an ADMIN, with no choice of what they become', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...lead('admin'),
      'POST /home-groups/group-1/close': () => json(200, { ...CLOSED, status: 'admin' }),
    })
    renderApp('/member/group')
    await screen.findByRole('option', { name: 'Harbour' })
    expect(screen.queryByLabelText('Afterwards I am')).toBeNull()
    await user.selectOptions(screen.getByLabelText('Join'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Close Riverside' }))
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    await screen.findByText(/is closed/)
    expect(api.calls.find((c) => c.key === 'POST /home-groups/group-1/close')?.body).toEqual({
      move_to_group_id: 'g2',
      former_leader_status: 'keep',
    })
  })

  it.each([
    ['group_not_empty', 409, /Others are still in this/],
    ['invalid_choice', 422, /does not fit you/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...lead(),
      'POST /home-groups/group-1/close': () => apiError(status, code),
    })
    renderApp('/member/group')
    await screen.findByRole('option', { name: 'Harbour' })
    await user.selectOptions(screen.getByLabelText('Join'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Close Riverside' }))
    await user.click(screen.getByRole('button', { name: 'Yes, close it' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('says when there is no other group to join', async () => {
    signedInAs(makeMe(), {
      ...lead(),
      [GROUPS]: () =>
        json(200, { items: [{ id: 'group-1', name: 'Riverside', leader_name: 'L' }] }),
    })
    renderApp('/member/group')
    expect(await screen.findByText(/There is no other open .* to join/)).toBeVisible()
  })

  it('shows an error with a retry when the groups cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(makeMe(), {
      ...lead(),
      [GROUPS]: () => (++attempts === 1 ? apiError(503, 'service_unavailable') : TWO()),
    })
    renderApp('/member/group')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('option', { name: 'Harbour' })).toBeVisible()
  })

  it('sends a provider home and a visitor to sign in, and the leader menu links to it', async () => {
    const api = signedInAs(makeMe(), {
      ...quiet,
      'GET /me': () => json(200, makePerson({ status: 'provider' })),
      [GROUPS]: TWO,
    })
    const { unmount } = renderApp('/member/group')
    expect(await screen.findByText(/^Welcome/)).toBeVisible()
    expect(api.count(GROUPS)).toBe(0)
    unmount()
    const out = mockApi({ [GROUPS]: TWO })
    const second = renderApp('/member/group')
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeVisible()
    expect(out.count(GROUPS)).toBe(0)
    second.unmount()
    signedInAs(makeMe(), lead())
    renderApp('/member')
    expect(await screen.findByRole('link', { name: /^My / })).toHaveAttribute(
      'href',
      '/member/group',
    )
  })
})
