import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, mockApi, renderApp, signedInAs } from '../../testUtils'

const LIST = 'GET /move-requests?limit=50&offset=0'
const GROUPS = 'GET /churches/church-1/home-groups'
const NOTES = 'GET /me/notifications?limit=50'
const quiet = { [NOTES]: () => json(200, { items: [], total: 0, unread_count: 0 }) }
const TWO = () =>
  json(200, {
    items: [
      { id: 'group-1', name: 'Riverside', leader_name: 'Lena Leader' },
      { id: 'g2', name: 'Harbour', leader_name: 'Hal Harbour' },
    ],
  })
// The signed-in person belongs to group-1 (Riverside); a leader there leads it.
const as = (status: string, extra = {}) => ({
  ...quiet,
  'GET /me': () => json(200, makePerson({ status: status as 'provider', ...extra })),
  [GROUPS]: TWO,
})
const lead = (status = 'verifier') =>
  as(status, { full_name: 'Lena Leader', leader: { name: 'Lena Leader' } })

const MOVE = {
  id: 'm1',
  person: { id: 'p7', name: 'Sam Searcher' },
  from_group: { id: 'group-1', name: 'Riverside' },
  to_group: { id: 'g2', name: 'Harbour' },
  agreed: { person: true, from_leader: false, to_leader: false },
  state: 'open',
  created_at: '2026-11-12T08:00:00Z',
}

describe('asking to move', () => {
  it('sends the chosen group and says the leaders were asked', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () => json(200, { items: [], total: 0 }),
      'POST /move-requests': () => json(201, MOVE),
    })
    renderApp('/member/moves')
    await screen.findByText('No moves.')
    expect(screen.queryByRole('option', { name: 'Riverside' })).toBeNull()
    await user.selectOptions(screen.getByLabelText('Move to'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Ask to move' }))
    expect(await screen.findByText(/sent to the leaders of both/)).toBeVisible()
    expect(api.calls.find((c) => c.key === 'POST /move-requests')?.body).toEqual({
      home_group_id: 'g2',
    })
  })

  it('keeps the button off until a group is chosen', async () => {
    signedInAs(makeMe(), { ...as('provider'), [LIST]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/moves')
    expect(await screen.findByRole('button', { name: 'Ask to move' })).toBeDisabled()
  })

  it.each([
    ['request_open', 409, /already have a move waiting/],
    ['invalid_choice', 422, /the .* you belong to/],
    ['leads_a_group', 409, /hands the .* on before moving/],
  ])('puts %s in words', async (code, status, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () => json(200, { items: [], total: 0 }),
      'POST /move-requests': () => apiError(status, code),
    })
    renderApp('/member/moves')
    await screen.findByRole('option', { name: 'Harbour' })
    await user.selectOptions(screen.getByLabelText('Move to'), 'g2')
    await user.click(screen.getByRole('button', { name: 'Ask to move' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('offers no form to a leader, and says to ask the ADMIN', async () => {
    signedInAs(makeMe(), { ...lead(), [LIST]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/moves')
    expect(await screen.findByText(/hands the .* on before moving/)).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Ask to move' })).toBeNull()
  })

  it('says when there is no other group', async () => {
    signedInAs(makeMe(), {
      ...as('provider'),
      [GROUPS]: () =>
        json(200, { items: [{ id: 'group-1', name: 'Riverside', leader_name: 'L' }] }),
      [LIST]: () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/moves')
    expect(await screen.findByText(/There is no other open .* in your/)).toBeVisible()
  })

  it('sends a pending applicant home and a signed-out visitor to sign in', async () => {
    const api = signedInAs(makeMe(), {
      ...as('pending'),
      [LIST]: () => json(200, { items: [], total: 0 }),
    })
    const { unmount } = renderApp('/member/moves')
    expect(await screen.findByRole('heading', { name: 'Your application' })).toBeVisible()
    expect(api.count(LIST)).toBe(0)
    unmount()
    const out = mockApi({ [LIST]: () => json(200, { items: [], total: 0 }) })
    renderApp('/member/moves')
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeVisible()
    expect(out.count(LIST)).toBe(0)
  })

  it('is linked from the home of a member and the leader menu', async () => {
    signedInAs(makeMe(), as('provider'))
    const { unmount } = renderApp('/member')
    expect(await screen.findByRole('link', { name: /^Move to another/ })).toHaveAttribute(
      'href',
      '/member/moves',
    )
    unmount()
    signedInAs(makeMe(), lead())
    renderApp('/member')
    expect(await screen.findByRole('link', { name: 'Moves' })).toHaveAttribute(
      'href',
      '/member/moves',
    )
  })
})

describe('the groups of the church', () => {
  it('shows a loading line, then an error with a retry when they cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(makeMe(), {
      ...as('provider'),
      [GROUPS]: () => (++attempts === 1 ? apiError(503, 'service_unavailable') : TWO()),
      [LIST]: () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/moves')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('option', { name: 'Harbour' })).toBeVisible()
  })

  it('says it is loading while the groups are on their way', async () => {
    signedInAs(makeMe(), {
      ...as('provider'),
      [GROUPS]: () => new Promise(() => {}) as never,
      [LIST]: () => json(200, { items: [], total: 0 }),
    })
    renderApp('/member/moves')
    expect(await screen.findAllByRole('status')).not.toHaveLength(0)
    expect(screen.queryByRole('button', { name: 'Ask to move' })).toBeNull()
  })
})

describe('the moves that concern me', () => {
  const withMoves = (routes: Record<string, unknown>, items = [MOVE]) => ({
    ...routes,
    [LIST]: () => json(200, { items, total: items.length }),
  })

  it('shows who agreed, and gives the member only a cancel', async () => {
    const api = signedInAs(
      makeMe(),
      withMoves(as('provider', { id: 'p7', full_name: 'Sam Searcher' }), [MOVE]) as never,
    )
    renderApp('/member/moves')
    const row = (await screen.findByText(/Sam Searcher: Riverside to Harbour/)).closest('li')!
    expect(within(row).getByText('The member agreed')).toBeVisible()
    expect(within(row).getByText('Waiting for the leader they leave')).toBeVisible()
    expect(within(row).getByText('Waiting for the leader they join')).toBeVisible()
    expect(within(row).queryByRole('button', { name: /^Agree/ })).toBeNull()
    expect(
      within(row).getByRole('button', { name: 'Cancel the move of Sam Searcher' }),
    ).toBeVisible()
    expect(api.count(LIST)).toBe(1)
  })

  it('lets the leader of the group they leave agree, and says they moved on the last one', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      withMoves(
        {
          ...lead(),
          'POST /move-requests/m1/agree': () =>
            json(200, {
              ...MOVE,
              state: 'completed',
              agreed: { person: true, from_leader: true, to_leader: true },
            }),
        },
        [{ ...MOVE, agreed: { person: true, from_leader: false, to_leader: true } }],
      ) as never,
    )
    renderApp('/member/moves')
    await user.click(
      await screen.findByRole('button', { name: 'Agree to the move of Sam Searcher' }),
    )
    expect(await screen.findByText('Sam Searcher moved.')).toBeVisible()
    expect(api.count('POST /move-requests/m1/agree')).toBe(1)
  })

  it('offers no agree to a leader who agreed already, or to one of neither group', async () => {
    signedInAs(
      makeMe(),
      withMoves(lead(), [
        { ...MOVE, agreed: { person: true, from_leader: true, to_leader: false } },
      ]) as never,
    )
    const { unmount } = renderApp('/member/moves')
    await screen.findByText(/Sam Searcher: Riverside to Harbour/)
    expect(screen.queryByRole('button', { name: /^Agree/ })).toBeNull()
    expect(screen.getByRole('button', { name: /^Cancel the move/ })).toBeVisible()
    unmount()
    signedInAs(
      makeMe(),
      withMoves(lead(), [
        { ...MOVE, from_group: { id: 'g8', name: 'North' }, to_group: { id: 'g9', name: 'South' } },
      ]) as never,
    )
    renderApp('/member/moves')
    await screen.findByText(/Sam Searcher: North to South/)
    expect(screen.queryByRole('button', { name: /^Agree|^Cancel the move/ })).toBeNull()
  })

  it.each([
    ['already_agreed', /You agreed already/],
    ['request_stale', /no longer in that/],
  ])('puts %s of an agreement in words', async (code, words) => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withMoves({ ...lead(), 'POST /move-requests/m1/agree': () => apiError(409, code) }) as never,
    )
    renderApp('/member/moves')
    await user.click(
      await screen.findByRole('button', { name: 'Agree to the move of Sam Searcher' }),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(words)
  })

  it('shows only the latest error: a failed agree is cleared by a cancel', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withMoves({
        ...lead(),
        'POST /move-requests/m1/agree': () => apiError(409, 'request_stale'),
        'POST /move-requests/m1/cancel': () => json(200, { ...MOVE, state: 'cancelled' }),
      }) as never,
    )
    renderApp('/member/moves')
    await user.click(
      await screen.findByRole('button', { name: 'Agree to the move of Sam Searcher' }),
    )
    await screen.findByText(/no longer in that/)
    await user.click(screen.getByRole('button', { name: 'Cancel the move of Sam Searcher' }))
    expect(await screen.findByText('The move was cancelled.')).toBeVisible()
    expect(screen.queryByText(/no longer in that/)).toBeNull()
  })

  it('cancels a move', async () => {
    const user = userEvent.setup({ delay: null })
    const api = signedInAs(
      makeMe(),
      withMoves({
        ...as('provider', { id: 'p7', full_name: 'Sam Searcher' }),
        'POST /move-requests/m1/cancel': () => json(200, { ...MOVE, state: 'cancelled' }),
      }) as never,
    )
    renderApp('/member/moves')
    await user.click(await screen.findByRole('button', { name: 'Cancel the move of Sam Searcher' }))
    expect(await screen.findByText('The move was cancelled.')).toBeVisible()
    expect(api.count('POST /move-requests/m1/cancel')).toBe(1)
  })

  it('shows decided moves without buttons, and the refusal of a late agree', async () => {
    const user = userEvent.setup({ delay: null })
    signedInAs(
      makeMe(),
      withMoves({ ...lead(), 'POST /move-requests/m1/agree': () => apiError(409, 'not_open') }, [
        MOVE,
        { ...MOVE, id: 'm2', state: 'completed' },
      ]) as never,
    )
    renderApp('/member/moves')
    const done = (await screen.findAllByText(/Sam Searcher: Riverside to Harbour/))[1].closest(
      'li',
    )!
    expect(within(done).getByText(/Done/)).toBeVisible()
    expect(within(done).queryByRole('button')).toBeNull()
    await user.click(screen.getAllByRole('button', { name: /^Agree/ })[0])
    expect(await screen.findByRole('alert')).toHaveTextContent(/decided already/)
  })

  it('shows an error with a retry when the list cannot be loaded', async () => {
    const user = userEvent.setup({ delay: null })
    let attempts = 0
    signedInAs(makeMe(), {
      ...as('provider'),
      [LIST]: () =>
        ++attempts === 1
          ? apiError(503, 'service_unavailable')
          : json(200, { items: [], total: 0 }),
    })
    renderApp('/member/moves')
    await user.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('No moves.')).toBeVisible()
  })
})

describe('notifications about moves', () => {
  it('reads each kind in words', async () => {
    signedInAs(makeMe(), {
      'GET /me': () => json(200, makePerson({ status: 'provider' })),
      [NOTES]: () =>
        json(200, {
          items: [
            'move_requested',
            'move_completed',
            'move_cancelled',
            'member_moved_in',
            'member_moved_out',
          ].map((kind, i) => ({
            id: `n${i}`,
            kind,
            subject: { name: 'Lena Leader' },
            created_at: '2026-11-12T08:00:00Z',
            read: false,
          })),
          total: 5,
          unread_count: 5,
        }),
    })
    renderApp('/member/notifications')
    expect(await screen.findByText(/Lena Leader asks to move/)).toBeVisible()
    expect(screen.getByText(/Lena Leader moved you/)).toBeVisible()
    expect(screen.getByText(/A move was cancelled by Lena Leader/)).toBeVisible()
    expect(screen.getByText(/Lena Leader joined your/)).toBeVisible()
    expect(screen.getByText(/Lena Leader left your/)).toBeVisible()
    expect(screen.queryByText('Something happened')).toBeNull()
  })
})
