import type { Page, Route } from '@playwright/test'

// A tiny fake of the API, so the layout checks need no backend or database.

export type Role = 'freelancer' | 'workhost' | 'organisation' | 'admin'

const ID = '11111111-1111-1111-1111-111111111111'

function me(role: Role) {
  return {
    id: ID,
    user_type: role,
    email: 'person@example.com',
    mobile_number: '+971500000001',
    full_name: role === 'organisation' ? null : 'Fatima Alexandrina Khan-Smithsonian',
    org_name: role === 'organisation' ? 'Acme Training and Development Services' : null,
    approval_status: role === 'organisation' ? 'approved' : null,
    created_at: '2026-10-01T10:00:00Z',
  }
}

const LABELS = [
  ['sk1', 'plumbing', 'skill'],
  ['sk2', 'carpentry', 'skill'],
  ['sk3', 'electrical installation and repair', 'skill'],
  ['lv1', 'basic', 'skill_level'],
  ['lv2', '80%', 'skill_level'],
  ['lg1', 'English', 'language'],
  ['lg2', 'Arabic', 'language'],
  ['tm1', 'weekends', 'timing'],
  ['nt1', 'Indian', 'nativity'],
].map(([id, label_name, label_type]) => ({ id, label_name, label_type, is_active: true }))

const PROFILE = {
  id: ID,
  full_name: 'Fatima Alexandrina Khan-Smithsonian',
  email: 'person@example.com',
  mobile_number: '+971500000001',
  whatsapp_availability: true,
  nationality: 'Indian',
  primary_language: 'Hindi',
  rate_per_hour: 50,
  rate_currency: 'AED',
  is_rate_negotiable: true,
  labels: [],
  created_at: '2026-10-01T10:00:00Z',
}

const RESULTS = Array.from({ length: 6 }, (_, index) => ({
  id: `22222222-2222-2222-2222-22222222222${index}`,
  full_name: `Anita Sharma-Venkataraman the ${index + 1}th`,
  nationality: 'Indian',
  primary_language: 'Hindi',
  whatsapp_availability: true,
  rate_per_hour: 50 + index,
  rate_currency: 'AED',
  is_rate_negotiable: index % 2 === 0,
  average_rating: 8.5,
  rating_count: 4,
  vouch_count: 2,
  skills: [
    { name: 'electrical installation and repair', level: '80%' },
    { name: 'plumbing', level: 'basic' },
    { name: 'carpentry', level: null },
  ],
  languages: ['English', 'Arabic'],
  timings: ['weekends'],
  nativity: [],
}))

const REPORTS = [
  {
    name: 'active_users',
    code: 'RP-02',
    title: 'Active users and logins',
    description: 'Users who logged in, and successful and failed logins.',
    filters: ['user_type'],
  },
]

const REPORT_DATA = {
  name: 'active_users',
  title: 'Active users and logins',
  window: { from: '2026-09-22T00:00:00Z', to: '2026-10-22T00:00:00Z' },
  row_count: 3,
  sections: [
    {
      title: 'Logins per day, user type and result',
      columns: [
        'day',
        'user_type',
        'successful_logins',
        'failed_logins',
        'distinct_users',
        'first_login_at',
        'last_login_at',
        'busiest_hour_of_the_day',
      ],
      rows: [
        [
          '2026-10-01',
          'freelancer',
          120,
          4,
          98,
          '2026-10-01T00:05:11Z',
          '2026-10-01T23:58:40Z',
          14,
        ],
        ['2026-10-02', 'workhost', 80, 9, 61, '2026-10-02T00:07:45Z', '2026-10-02T23:41:02Z', 10],
        [
          '2026-10-03',
          'organisation',
          12,
          0,
          12,
          '2026-10-03T06:30:00Z',
          '2026-10-03T17:05:00Z',
          9,
        ],
      ],
    },
  ],
}

// Tokens for the fake API are made up on the spot, never written into the source.
const fakeToken = () => `t-${Math.random().toString(36).slice(2)}`

function body(route: Route, status: number, data?: unknown) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: data === undefined ? '' : JSON.stringify(data),
  })
}

/** Answer API calls with fixed data. Pass a role to start signed in as that role. */
export async function mockApi(page: Page, role: Role | null) {
  if (role) {
    await page.addInitScript(() => {
      sessionStorage.setItem('skills.refresh_token', 'e2e-refresh')
    })
  }
  await page.route('**/api/v1/**', (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api/v1', '')
    const method = route.request().method()
    if (method === 'POST' && path === '/auth/refresh') {
      return body(route, 200, {
        access_token: fakeToken(),
        refresh_token: fakeToken(),
        token_type: 'bearer', // secret-scan:allow (a label, not a secret)
        expires_in: 900,
      })
    }
    if (method !== 'GET') return body(route, 404, { error: { code: 'not_found' } })
    if (path === '/me' && role) return body(route, 200, me(role))
    if (path === '/labels') return body(route, 200, LABELS)
    if (path === '/freelancers/me') return body(route, 200, PROFILE)
    if (path === '/organisations') {
      return body(route, 200, [{ id: 'org-1', org_name: 'Acme Training and Development' }])
    }
    if (path === '/search/freelancers') {
      return body(route, 200, { items: RESULTS, total: 40, page: 1, page_size: 12 })
    }
    if (path === '/reports') return body(route, 200, REPORTS)
    if (path === '/reports/active_users') return body(route, 200, REPORT_DATA)
    return body(route, 404, { error: { code: 'not_found', message: 'no mock', details: {} } })
  })
}
