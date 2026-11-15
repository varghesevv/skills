import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, makePerson, renderApp, signedInAs } from '../../../testUtils'
import { ALL_LABELS } from '../provider/testData'

const ui = () => userEvent.setup({ delay: null })
const quiet = {
  'GET /me/notifications?limit=50': () => json(200, { items: [], total: 0, unread_count: 0 }),
}
/** The OWNER, who manages the labels. */
function asOwner(routes: Record<string, () => Response> = {}) {
  return signedInAs(makeMe(), {
    ...quiet,
    'GET /me': () => json(200, makePerson({ status: 'owner' })),
    ...routes,
  })
}

describe('label management', () => {
  const LIST = 'GET /labels?include_inactive=true'
  const labels = [
    ...ALL_LABELS,
    { ...ALL_LABELS[1], id: 'sk3', label_name: 'old', is_active: false },
  ]

  it('shows labels of the chosen kind, with inactive ones marked', async () => {
    const user = ui()
    asOwner({ [LIST]: () => json(200, labels) })
    renderApp('/member/labels')
    expect(await screen.findByRole('heading', { name: 'plumbing' })).toBeVisible()
    expect(screen.getByText('Inactive')).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'English' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Kind of label'), 'Languages')
    expect(await screen.findByRole('heading', { name: 'English' })).toBeVisible()
  })

  it('adds a label of the chosen kind', async () => {
    const user = ui()
    const api = asOwner({
      [LIST]: () => json(200, labels),
      'POST /labels': () => json(201, { ...ALL_LABELS[0], id: 'new', label_name: 'welding' }),
    })
    renderApp('/member/labels')
    await user.type(await screen.findByLabelText('New label name'), '  welding ')
    await user.click(screen.getByRole('button', { name: 'Add label' }))
    await waitFor(() => expect(api.count('POST /labels')).toBe(1))
    expect(api.last('POST /labels')?.body).toEqual({ label_name: 'welding', label_type: 'skill' })
  })

  it('does not add an empty name, and explains a duplicate', async () => {
    const user = ui()
    const api = asOwner({
      [LIST]: () => json(200, labels),
      'POST /labels': () => apiError(409, 'label_exists'),
    })
    renderApp('/member/labels')
    await user.click(await screen.findByRole('button', { name: 'Add label' }))
    expect(await screen.findByText('This field is required.')).toBeVisible()
    expect(api.count('POST /labels')).toBe(0)

    await user.type(screen.getByLabelText('New label name'), 'plumbing')
    await user.click(screen.getByRole('button', { name: 'Add label' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
  })

  it('renames a label', async () => {
    const user = ui()
    const api = asOwner({
      [LIST]: () => json(200, labels),
      [`PATCH /labels/${ALL_LABELS[0].id}`]: () =>
        json(200, { ...ALL_LABELS[0], label_name: 'pipes' }),
    })
    renderApp('/member/labels')
    await user.click(await screen.findByRole('button', { name: 'Rename: plumbing' }))
    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'pipes')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.count(`PATCH /labels/${ALL_LABELS[0].id}`)).toBe(1))
    expect(api.last(`PATCH /labels/${ALL_LABELS[0].id}`)?.body).toEqual({ label_name: 'pipes' })
  })

  it('deactivates and reactivates labels', async () => {
    const user = ui()
    const api = asOwner({
      [LIST]: () => json(200, labels),
      [`PATCH /labels/${ALL_LABELS[0].id}`]: () =>
        json(200, { ...ALL_LABELS[0], is_active: false }),
      'PATCH /labels/sk3': () => json(200, { ...labels[7], is_active: true }),
    })
    renderApp('/member/labels')
    await user.click(await screen.findByRole('button', { name: 'Deactivate: plumbing' }))
    await waitFor(() => expect(api.count(`PATCH /labels/${ALL_LABELS[0].id}`)).toBe(1))
    expect(api.last(`PATCH /labels/${ALL_LABELS[0].id}`)?.body).toEqual({ is_active: false })

    await user.click(screen.getByRole('button', { name: 'Activate: old' }))
    await waitFor(() => expect(api.count('PATCH /labels/sk3')).toBe(1))
    expect(api.last('PATCH /labels/sk3')?.body).toEqual({ is_active: true })
  })
})
