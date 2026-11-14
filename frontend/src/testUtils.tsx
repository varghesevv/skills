import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import type { Me, PersonMe } from './api/types'
import App from './App'
import { setTokens } from './auth/tokenStore'

// Passwords used in tests are generated, never written into the source.
export const PASSWORD = `pw-${Math.random().toString(36).slice(2).padEnd(12, 'x')}`

export type ApiRequest = { body: unknown; headers: Headers }
export type Handler = (request: ApiRequest) => Response | Promise<Response>

export function json(status: number, body?: unknown, headers?: Record<string, string>): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers })
}

export function apiError(
  status: number,
  code: string,
  details: Record<string, unknown> = {},
  headers?: Record<string, string>,
): Response {
  return json(status, { error: { code, message: 'server message', details } }, headers)
}

export function tokens(label = '1') {
  return {
    access_token: `access-${label}`,
    refresh_token: `refresh-${label}`,
    token_type: 'bearer', // secret-scan:allow (a label, not a secret)
    expires_in: 900,
  }
}

export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    user_type: 'freelancer',
    email: 'f@example.com',
    mobile_number: '+971500000001',
    full_name: 'Fatima Khan',
    org_name: null,
    approval_status: null,
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}

export function makePerson(overrides: Partial<PersonMe> = {}): PersonMe {
  return {
    user_type: 'person',
    id: '22222222-2222-2222-2222-222222222222',
    full_name: 'Nadia Applicant',
    email: 'n@example.com',
    mobile_number: '+971500000002',
    status: 'pending',
    requested_status: 'searcher',
    church: { id: 'church-1', name: 'Grace Church' },
    home_group: { id: 'group-1', name: 'Riverside' },
    leader: { name: 'Lena Leader' },
    status_set_by: null,
    flagged_for_recheck: false,
    vouch_count: 0,
    ...overrides,
  }
}

/** Replace fetch with handlers keyed like "POST /auth/login" (path without /api/v1). */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { key: string; body: unknown; headers: Headers }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input).replace('/api/v1', '')}`
    const headers = new Headers(init?.headers)
    const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
    calls.push({ key, body, headers })
    const handler = routes[key]
    return handler ? handler({ body, headers }) : apiError(404, 'not_found')
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    calls,
    count: (key: string) => calls.filter((call) => call.key === key).length,
    last: (key: string) => calls.filter((call) => call.key === key).at(-1),
  }
}

export function renderApp(route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  // The client is returned so that a test can look at what is cached and what was invalidated.
  return { ...view, queryClient: client }
}

export const OLD_REFRESH = 'refresh-old'

/** A returning visitor: a refresh token is stored, so the app restores the session. */
export function signedInAs(me: Me = makeMe(), routes: Record<string, Handler> = {}) {
  setTokens('gone', OLD_REFRESH)
  return mockApi({
    'POST /auth/refresh': () => json(200, tokens('2')),
    'GET /me': () => json(200, me),
    'POST /auth/logout': () => json(204),
    ...routes,
  })
}
