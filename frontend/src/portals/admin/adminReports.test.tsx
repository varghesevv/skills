import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiError, json, makeMe, renderApp, signedInAs } from '../../testUtils'

const ui = () => userEvent.setup({ delay: null })
const admin = makeMe({ user_type: 'admin', full_name: 'Site Admin', email: 'a@example.com' })

const info = (name: string, title: string, filters: string[] = []) => ({
  name,
  code: 'RP-00',
  title,
  description: `About ${title}`,
  filters,
})
const REPORTS = [
  info('registrations_per_day', 'Registrations per day'),
  info('active_users', 'Active users and logins', ['user_type']),
  info('top_rated', 'Top rated freelancers', ['min_ratings']),
  info('availability_overview', 'Availability overview'),
]
const LIST = 'GET /reports'
const empty = (name: string) => ({
  name,
  title: name,
  window: { from: '2026-10-01T00:00:00Z', to: '2026-11-01T00:00:00Z' },
  row_count: 0,
  sections: [],
})

function card(title: string) {
  return within(screen.getByRole('region', { name: title }))
}

describe('report pages', () => {
  it('runs a report for the default dates and shows the table', async () => {
    const user = ui()
    signedInAs(admin, {
      [LIST]: () => json(200, REPORTS),
      'GET /reports/registrations_per_day?format=json': () =>
        json(200, {
          ...empty('registrations_per_day'),
          row_count: 1,
          sections: [{ title: 'Per day', columns: ['day', 'count'], rows: [['2026-10-01', 4]] }],
        }),
    })
    renderApp('/admin/reports')
    await screen.findByRole('region', { name: 'Registrations per day' })
    await user.click(card('Registrations per day').getByRole('button', { name: 'Run report' }))
    expect(await screen.findByRole('cell', { name: '2026-10-01' })).toBeVisible()
  })

  it('sends the dates and the report filters', async () => {
    const user = ui()
    const url =
      'GET /reports/active_users?from=2026-10-01&to=2026-10-31&user_type=workhost&format=json'
    const api = signedInAs(admin, {
      [LIST]: () => json(200, REPORTS),
      [url]: () => json(200, empty('active_users')),
    })
    renderApp('/admin/reports')
    await screen.findByRole('region', { name: 'Active users and logins' })
    const users = card('Active users and logins')
    await user.type(users.getByLabelText('From'), '2026-10-01')
    await user.type(users.getByLabelText('To'), '2026-10-31')
    await user.selectOptions(users.getByLabelText('User type'), 'Work host')
    await user.click(users.getByRole('button', { name: 'Run report' }))
    expect(await users.findByText('Nothing to show yet.')).toBeVisible()
    expect(api.count(url)).toBe(1)
  })

  it('checks the rating count before calling the API', async () => {
    const user = ui()
    const api = signedInAs(admin, { [LIST]: () => json(200, REPORTS) })
    renderApp('/admin/reports')
    await screen.findByRole('region', { name: 'Top rated freelancers' })
    const top = card('Top rated freelancers')
    await user.type(top.getByLabelText('At least this many ratings'), '0')
    await user.click(top.getByRole('button', { name: 'Run report' }))
    expect(await top.findByText('Enter a whole number from 1 to 1000.')).toBeVisible()
    expect(api.calls.filter((call) => call.key.startsWith('GET /reports/'))).toHaveLength(0)
  })

  it('keeps the availability report to 93 days', async () => {
    const user = ui()
    const api = signedInAs(admin, { [LIST]: () => json(200, REPORTS) })
    renderApp('/admin/reports')
    await screen.findByRole('region', { name: 'Availability overview' })
    const overview = card('Availability overview')
    await user.type(overview.getByLabelText('From'), '2026-01-01')
    await user.type(overview.getByLabelText('To'), '2026-06-01')
    await user.click(overview.getByRole('button', { name: 'Run report' }))
    expect(await overview.findByText('A report covers at most 93 days.')).toBeVisible()
    expect(api.calls.filter((call) => call.key.startsWith('GET /reports/'))).toHaveLength(0)
  })
})

describe('report history', () => {
  const RUNS = 'GET /reports/runs?page=1&page_size=10'
  const run = (overrides: Record<string, unknown> = {}) => ({
    id: 'run-1',
    report_name: 'top_rated',
    window_from: '2026-10-01T00:00:00Z',
    window_to: '2026-10-08T00:00:00Z',
    started_at: '2026-10-08T06:00:00Z',
    finished_at: '2026-10-08T06:00:05Z',
    status: 'succeeded',
    row_count: 12,
    error_message: null,
    has_files: true,
    ...overrides,
  })
  const runPage = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 10 })

  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:report')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })
  afterEach(() => vi.restoreAllMocks())

  it('lists runs and downloads a file', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, REPORTS),
      [RUNS]: () =>
        json(
          200,
          runPage([
            run(),
            run({ id: 'run-2', status: 'failed', has_files: false, error_message: 'boom' }),
          ]),
        ),
      'GET /reports/runs/run-1/download?format=csv': () =>
        new Response('a,b', {
          status: 200,
          headers: { 'Content-Disposition': 'attachment; filename="top_rated.csv"' },
        }),
    })
    renderApp('/admin/report-history')
    await user.click(await screen.findByRole('button', { name: 'CSV: Top rated freelancers' }))
    await waitFor(() => expect(api.count('GET /reports/runs/run-1/download?format=csv')).toBe(1))
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled())
    expect(screen.getByText('boom')).toBeVisible()
    expect(screen.getByText('No files')).toBeVisible()
  })

  it('runs and keeps a report for the chosen dates', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, REPORTS),
      [RUNS]: () => json(200, runPage([])),
      'POST /reports/top_rated/run': () => json(201, run()),
    })
    renderApp('/admin/report-history')
    // The report list loads after the form appears, so wait for its options.
    await screen.findAllByRole('option', { name: 'Top rated freelancers' })
    await user.selectOptions(
      screen.getByLabelText('Report', { selector: 'select[name="keep_report"]' }),
      'Top rated freelancers',
    )
    await user.type(screen.getByLabelText('From'), '2026-10-01')
    await user.type(screen.getByLabelText('To'), '2026-10-07')
    await user.click(screen.getByRole('button', { name: 'Run and keep' }))
    expect(await screen.findByText('The report ran and its files are kept.')).toBeVisible()
    expect(api.last('POST /reports/top_rated/run')?.body).toEqual({
      date_from: '2026-10-01',
      date_to: '2026-10-07',
    })
  })

  it('asks for a report and dates first', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [LIST]: () => json(200, REPORTS),
      [RUNS]: () => json(200, runPage([])),
    })
    renderApp('/admin/report-history')
    await user.click(await screen.findByRole('button', { name: 'Run and keep' }))
    expect(await screen.findByText('Choose a report', { selector: '[id$="-error"]' })).toBeVisible()
    expect(api.calls.filter((call) => call.key.startsWith('POST /reports'))).toHaveLength(0)
  })
})

describe('schedules', () => {
  const schedule = {
    report_name: 'users_registered_daily',
    cron_expression: '5 0 * * *',
    timezone: 'Asia/Dubai',
    is_enabled: true,
  }
  const SCHEDULES = 'GET /reports/schedules'
  const PUT = 'PUT /reports/schedules/users_registered_daily'
  const reports = [info('users_registered_daily', 'Users registered in the last day')]

  it('saves a changed schedule', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [SCHEDULES]: () => json(200, [schedule]),
      [LIST]: () => json(200, reports),
      [PUT]: () => json(200, { ...schedule, cron_expression: '10 1 * * *', is_enabled: false }),
    })
    renderApp('/admin/report-schedules')
    const cron = await screen.findByLabelText('When (cron)')
    await user.clear(cron)
    await user.type(cron, '10 1 * * *')
    await user.click(screen.getByLabelText('Run on this schedule'))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Saved.')
    expect(api.last(PUT)?.body).toEqual({
      cron_expression: '10 1 * * *',
      timezone: 'Asia/Dubai',
      is_enabled: false,
    })
  })

  it('does not send a cron expression with the wrong number of fields', async () => {
    const user = ui()
    const api = signedInAs(admin, {
      [SCHEDULES]: () => json(200, [schedule]),
      [LIST]: () => json(200, reports),
    })
    renderApp('/admin/report-schedules')
    const cron = await screen.findByLabelText('When (cron)')
    await user.clear(cron)
    await user.type(cron, 'every day')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(
      await screen.findByText('Enter five fields: minute hour day month weekday.'),
    ).toBeVisible()
    expect(api.count(PUT)).toBe(0)
  })

  it('shows the server message when the schedule is rejected', async () => {
    const user = ui()
    signedInAs(admin, {
      [SCHEDULES]: () => json(200, [schedule]),
      [LIST]: () => json(200, reports),
      [PUT]: () => apiError(422, 'invalid_schedule'),
    })
    renderApp('/admin/report-schedules')
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('not valid')
  })
})
