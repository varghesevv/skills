import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, makeMe, renderApp, signedInAs } from '../../testUtils'
import { ALL_LABELS } from '../freelancer/testData'
import { PERSON_ID, makePerson, makeResult, page } from '../workhost/testData'

const ui = () => userEvent.setup({ delay: null })
const ORG_ID = '33333333-3333-3333-3333-333333333333'
const org = makeMe({
  id: ORG_ID,
  user_type: 'organisation',
  full_name: null,
  org_name: 'Acme Training',
  email: 'o@example.com',
  approval_status: 'approved',
})
const PERSON_LINK = `/organisations/me/freelancers/${PERSON_ID}`

function asOrg(
  routes: Parameters<typeof signedInAs>[1] = {},
  me: Parameters<typeof signedInAs>[0] = org,
) {
  return signedInAs(me, { 'GET /labels': () => json(200, ALL_LABELS), ...routes })
}

const vouched = (overrides: Record<string, unknown> = {}) => ({
  freelancer_id: PERSON_ID,
  full_name: 'Anita Sharma',
  nationality: 'Indian',
  primary_language: 'Hindi',
  status: 'approved',
  is_active: true,
  created_at: '2026-10-05T10:00:00Z',
  ...overrides,
})

describe('navigation', () => {
  it('lists the organisation pages', async () => {
    asOrg()
    renderApp('/organisation')
    const nav = await screen.findByRole('navigation', { name: 'Main navigation' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Dashboard', 'Vouched freelancers', 'Find freelancers', 'Reports', 'Profile'])
  })
})

describe('profile', () => {
  const profile = {
    id: ORG_ID,
    email: 'o@example.com',
    org_name: 'Acme Training',
    mobile_number: '+971500000003',
    approval_status: 'pending',
    created_at: '2026-10-01T10:00:00Z',
  }

  it('shows the approval status and saves changes', async () => {
    const user = ui()
    const api = asOrg({
      'GET /organisations/me': () => json(200, profile),
      'PUT /organisations/me': () => json(200, { ...profile, org_name: 'Acme Academy' }),
    })
    renderApp('/organisation/profile')
    expect(await screen.findByText('Waiting for admin approval')).toBeVisible()

    const name = screen.getByLabelText('Organisation Name')
    await user.clear(name)
    await user.type(name, 'Acme Academy')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last('PUT /organisations/me')?.body).toEqual({
      org_name: 'Acme Academy',
      mobile_number: '+971500000003',
    })
  })

  it('does not save a name that is too short', async () => {
    const user = ui()
    const api = asOrg({ 'GET /organisations/me': () => json(200, profile) })
    renderApp('/organisation/profile')
    const name = await screen.findByLabelText('Organisation Name')
    await user.clear(name)
    await user.type(name, 'A')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Enter 2 to 200 characters.')).toBeVisible()
    expect(api.count('PUT /organisations/me')).toBe(0)
  })
})

describe('vouched freelancers', () => {
  const LIST = 'GET /organisations/me/freelancers?page=1&page_size=10'

  it('shows names and statuses, and says when there are none', async () => {
    asOrg({ [LIST]: () => json(200, page([vouched({ status: 'pending' })], 1)) })
    renderApp('/organisation/freelancers')
    expect(await screen.findByRole('link', { name: 'Anita Sharma' })).toBeVisible()
    expect(screen.getByText('Waiting for the freelancer')).toBeVisible()
  })

  it('shows an empty message', async () => {
    asOrg({ [LIST]: () => json(200, page([], 0)) })
    renderApp('/organisation/freelancers')
    expect(await screen.findByText('You have not vouched for anyone yet.')).toBeVisible()
  })

  it('asks for confirmation before revoking', async () => {
    const user = ui()
    let revoked = false
    const api = asOrg({
      [LIST]: () => json(200, page([vouched({ status: revoked ? 'revoked' : 'approved' })], 1)),
      [`DELETE ${PERSON_LINK}`]: () => {
        revoked = true
        return json(204)
      },
    })
    renderApp('/organisation/freelancers')
    await user.click(await screen.findByRole('button', { name: 'Revoke: Anita Sharma' }))
    expect(api.count(`DELETE ${PERSON_LINK}`)).toBe(0)
    await user.click(screen.getByRole('button', { name: 'Yes, revoke: Anita Sharma' }))
    expect(await screen.findByRole('button', { name: 'Vouch again: Anita Sharma' })).toBeVisible()
    expect(api.count(`DELETE ${PERSON_LINK}`)).toBe(1)
  })

  it('lets the organisation back out of a revoke', async () => {
    const user = ui()
    const api = asOrg({ [LIST]: () => json(200, page([vouched()], 1)) })
    renderApp('/organisation/freelancers')
    await user.click(await screen.findByRole('button', { name: 'Revoke: Anita Sharma' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByRole('button', { name: 'Revoke: Anita Sharma' })).toBeVisible()
    expect(api.count(`DELETE ${PERSON_LINK}`)).toBe(0)
  })

  it('vouches again after a revoke', async () => {
    const user = ui()
    const api = asOrg({
      [LIST]: () => json(200, page([vouched({ status: 'revoked', is_active: false })], 1)),
      [`POST ${PERSON_LINK}`]: () => json(201, vouched({ status: 'pending' })),
    })
    renderApp('/organisation/freelancers')
    await user.click(await screen.findByRole('button', { name: 'Vouch again: Anita Sharma' }))
    await waitFor(() => expect(api.count(`POST ${PERSON_LINK}`)).toBe(1))
  })
})

describe('finding someone to vouch for', () => {
  const SEARCH = 'GET /search/freelancers?page=1&page_size=12'
  const DETAIL = `GET /freelancers/${PERSON_ID}`
  const RATINGS = `GET /freelancers/${PERSON_ID}/ratings?page=1&page_size=10`

  it('links search results to the organisation detail page', async () => {
    asOrg({ [SEARCH]: () => json(200, page([makeResult()])) })
    renderApp('/organisation/search')
    const link = await screen.findByRole('link', { name: 'Anita Sharma' })
    expect(link).toHaveAttribute('href', `/organisation/freelancers/${PERSON_ID}`)
  })

  it('vouches from the detail page and hides rating and contact details', async () => {
    const user = ui()
    const api = asOrg({
      [DETAIL]: () => json(200, makePerson({ mobile_number: null })),
      [RATINGS]: () => json(200, page([], 0)),
      [`POST ${PERSON_LINK}`]: () => json(201, vouched({ status: 'pending' })),
    })
    renderApp(`/organisation/freelancers/${PERSON_ID}`)
    expect(await screen.findByRole('heading', { name: 'Anita Sharma' })).toBeVisible()
    expect(screen.queryByText('Contact')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Score (1 to 10)')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Vouch for this freelancer' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Vouch sent.')
    expect(api.count(`POST ${PERSON_LINK}`)).toBe(1)
  })

  it('shows a clear message when the vouch already exists', async () => {
    const user = ui()
    asOrg({
      [DETAIL]: () => json(200, makePerson({ mobile_number: null })),
      [RATINGS]: () => json(200, page([], 0)),
      [`POST ${PERSON_LINK}`]: () => apiError(409, 'already_vouched'),
    })
    renderApp(`/organisation/freelancers/${PERSON_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Vouch for this freelancer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You already vouch for this freelancer.',
    )
  })

  it('does not offer to vouch until the organisation is approved', async () => {
    asOrg(
      {
        [DETAIL]: () => json(200, makePerson({ mobile_number: null })),
        [RATINGS]: () => json(200, page([], 0)),
      },
      { ...org, approval_status: 'pending' },
    )
    renderApp(`/organisation/freelancers/${PERSON_ID}`)
    expect(await screen.findByText(/must be approved by an admin/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Vouch for this freelancer' })).toBeDisabled()
  })

  it('says so when the organisation already vouches', async () => {
    asOrg({
      [DETAIL]: () =>
        json(
          200,
          makePerson({ mobile_number: null, vouched_by: [{ org_id: ORG_ID, org_name: 'Acme' }] }),
        ),
      [RATINGS]: () => json(200, page([], 0)),
    })
    renderApp(`/organisation/freelancers/${PERSON_ID}`)
    expect(await screen.findByText('You vouch for this freelancer.')).toBeVisible()
    expect(
      screen.queryByRole('button', { name: 'Vouch for this freelancer' }),
    ).not.toBeInTheDocument()
  })
})

describe('reports', () => {
  const REPORT = {
    name: 'vouching_summary',
    code: 'RP-05',
    title: 'Vouching summary',
    description: 'How many freelancers you vouch for.',
    filters: [],
  }
  const RUN = 'GET /reports/vouching_summary?format=json'

  it('runs the report and shows the table without ids', async () => {
    const user = ui()
    asOrg({
      'GET /reports': () => json(200, [REPORT]),
      [RUN]: () =>
        json(200, {
          name: REPORT.name,
          title: REPORT.title,
          window: { from: '2026-09-01T00:00:00Z', to: '2026-10-01T00:00:00Z' },
          row_count: 1,
          sections: [
            {
              title: 'Organisation vouching summary',
              columns: ['org_id', 'organisation', 'freelancers'],
              rows: [[ORG_ID, 'Acme Training', 3]],
            },
          ],
        }),
    })
    renderApp('/organisation/reports')
    await user.click(await screen.findByRole('button', { name: 'Run report' }))
    expect(await screen.findByRole('cell', { name: 'Acme Training' })).toBeVisible()
    expect(screen.getByRole('cell', { name: '3' })).toBeVisible()
    expect(screen.queryByText(ORG_ID)).not.toBeInTheDocument()
  })

  it('sends the chosen date range', async () => {
    const user = ui()
    const ranged = 'GET /reports/vouching_summary?from=2026-10-01&to=2026-10-31&format=json'
    const api = asOrg({
      'GET /reports': () => json(200, [REPORT]),
      [ranged]: () =>
        json(200, {
          name: REPORT.name,
          title: REPORT.title,
          window: { from: '2026-10-01T00:00:00Z', to: '2026-11-01T00:00:00Z' },
          row_count: 0,
          sections: [],
        }),
    })
    renderApp('/organisation/reports')
    await user.type(await screen.findByLabelText('From'), '2026-10-01')
    await user.type(screen.getByLabelText('To'), '2026-10-31')
    await user.click(screen.getByRole('button', { name: 'Run report' }))
    expect(await screen.findByText('Nothing to show yet.')).toBeVisible()
    expect(api.count(ranged)).toBe(1)
  })

  it('asks for both dates and a sensible order before calling the API', async () => {
    const user = ui()
    const api = asOrg({ 'GET /reports': () => json(200, [REPORT]) })
    renderApp('/organisation/reports')
    await user.type(await screen.findByLabelText('From'), '2026-10-01')
    await user.click(screen.getByRole('button', { name: 'Run report' }))
    expect(await screen.findByText('Give both dates, or leave both empty.')).toBeVisible()

    await user.type(screen.getByLabelText('To'), '2026-09-01')
    await user.click(screen.getByRole('button', { name: 'Run report' }))
    expect(await screen.findByText('The end date must not be before the start date.')).toBeVisible()
    expect(api.calls.filter((call) => call.key.startsWith('GET /reports/'))).toHaveLength(0)
  })

  it('shows an error when the report fails', async () => {
    const user = ui()
    asOrg({
      'GET /reports': () => json(200, [REPORT]),
      [RUN]: () => apiError(500, 'internal_error'),
    })
    renderApp('/organisation/reports')
    await user.click(await screen.findByRole('button', { name: 'Run report' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
  })
})
