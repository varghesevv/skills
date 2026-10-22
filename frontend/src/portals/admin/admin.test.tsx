import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, renderApp, signedInAs } from '../../testUtils'
import { ALL_LABELS } from '../freelancer/testData'

const ui = () => userEvent.setup({ delay: null })
const admin = makeMe({
  id: '44444444-4444-4444-4444-444444444444',
  user_type: 'admin',
  full_name: 'Site Admin',
  email: 'a@example.com',
})

const org = (overrides: Record<string, unknown> = {}) => ({
  id: 'org-1',
  org_name: 'Acme Training',
  email: 'o@example.com',
  mobile_number: '+971500000003',
  approval_status: 'pending',
  created_at: '2026-10-05T10:00:00Z',
  ...overrides,
})
const orgPage = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 10 })
const ORGS = (status: string) => `GET /admin/organisations?status=${status}&page=1&page_size=10`

describe('navigation', () => {
  it('lists the admin pages', async () => {
    signedInAs(admin)
    renderApp('/admin')
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Dashboard', 'Organisations', 'Reports', 'Report history', 'Schedules', 'Labels'])
  })
})

describe('organisation approvals', () => {
  it('approves a waiting organisation and refreshes the list', async () => {
    const user = ui()
    let approved = false
    const api = signedInAs(admin, {
      [ORGS('pending')]: () => json(200, orgPage(approved ? [] : [org()])),
      'POST /admin/organisations/org-1/approve': () => {
        approved = true
        return json(200, org({ approval_status: 'approved' }))
      },
    })
    renderApp('/admin/organisations')
    expect(await screen.findByRole('heading', { name: 'Acme Training' })).toBeVisible()
    expect(screen.getByText('o@example.com')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Approve: Acme Training' }))
    expect(await screen.findByText('No organisations in this list.')).toBeVisible()
    expect(api.count('POST /admin/organisations/org-1/approve')).toBe(1)
  })

  it('rejects an organisation', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [ORGS('pending')]: () => json(200, orgPage([org()])),
      'POST /admin/organisations/org-1/reject': () =>
        json(200, org({ approval_status: 'rejected' })),
    })
    renderApp('/admin/organisations')
    await user.click(await screen.findByRole('button', { name: 'Reject: Acme Training' }))
    await waitFor(() => expect(api.count('POST /admin/organisations/org-1/reject')).toBe(1))
  })

  it('switches lists, and offers only the opposite decision', async () => {
    const user = ui()
    signedInAs(admin, {
      [ORGS('pending')]: () => json(200, orgPage([])),
      [ORGS('approved')]: () => json(200, orgPage([org({ approval_status: 'approved' })])),
    })
    renderApp('/admin/organisations')
    await user.click(await screen.findByRole('button', { name: 'Approved' }))
    expect(await screen.findByRole('button', { name: 'Reject: Acme Training' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Approve: Acme Training' })).not.toBeInTheDocument()
  })

  it('shows an error when the decision fails', async () => {
    const user = ui()
    signedInAs(admin, {
      [ORGS('pending')]: () => json(200, orgPage([org()])),
      'POST /admin/organisations/org-1/approve': () => apiError(404, 'not_found'),
    })
    renderApp('/admin/organisations')
    await user.click(await screen.findByRole('button', { name: 'Approve: Acme Training' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('no longer exists')
  })
})

describe('label management', () => {
  const LIST = 'GET /labels?include_inactive=true'
  const labels = [
    ...ALL_LABELS,
    { ...ALL_LABELS[1], id: 'sk3', label_name: 'old', is_active: false },
  ]

  it('shows labels of the chosen kind, with inactive ones marked', async () => {
    const user = ui()
    signedInAs(admin, { [LIST]: () => json(200, labels) })
    renderApp('/admin/labels')
    expect(await screen.findByRole('heading', { name: 'plumbing' })).toBeVisible()
    expect(screen.getByText('Inactive')).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'English' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Kind of label'), 'Languages')
    expect(await screen.findByRole('heading', { name: 'English' })).toBeVisible()
  })

  it('adds a label of the chosen kind', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, labels),
      'POST /labels': () => json(201, { ...ALL_LABELS[0], id: 'new', label_name: 'welding' }),
    })
    renderApp('/admin/labels')
    await user.type(await screen.findByLabelText('New label name'), '  welding ')
    await user.click(screen.getByRole('button', { name: 'Add label' }))
    await waitFor(() => expect(api.count('POST /labels')).toBe(1))
    expect(api.last('POST /labels')?.body).toEqual({ label_name: 'welding', label_type: 'skill' })
  })

  it('does not add an empty name, and explains a duplicate', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, labels),
      'POST /labels': () => apiError(409, 'label_exists'),
    })
    renderApp('/admin/labels')
    await user.click(await screen.findByRole('button', { name: 'Add label' }))
    expect(await screen.findByText('This field is required.')).toBeVisible()
    expect(api.count('POST /labels')).toBe(0)

    await user.type(screen.getByLabelText('New label name'), 'plumbing')
    await user.click(screen.getByRole('button', { name: 'Add label' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already exists')
  })

  it('renames a label', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, labels),
      [`PATCH /labels/${ALL_LABELS[0].id}`]: () =>
        json(200, { ...ALL_LABELS[0], label_name: 'pipes' }),
    })
    renderApp('/admin/labels')
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
    const api = signedInAs(admin, {
      [LIST]: () => json(200, labels),
      [`PATCH /labels/${ALL_LABELS[0].id}`]: () =>
        json(200, { ...ALL_LABELS[0], is_active: false }),
      'PATCH /labels/sk3': () => json(200, { ...labels[7], is_active: true }),
    })
    renderApp('/admin/labels')
    await user.click(await screen.findByRole('button', { name: 'Deactivate: plumbing' }))
    await waitFor(() => expect(api.count(`PATCH /labels/${ALL_LABELS[0].id}`)).toBe(1))
    expect(api.last(`PATCH /labels/${ALL_LABELS[0].id}`)?.body).toEqual({ is_active: false })

    await user.click(screen.getByRole('button', { name: 'Activate: old' }))
    await waitFor(() => expect(api.count('PATCH /labels/sk3')).toBe(1))
    expect(api.last('PATCH /labels/sk3')?.body).toEqual({ is_active: true })
  })
})
