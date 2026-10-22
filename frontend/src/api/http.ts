import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '../auth/tokenStore'
import type { TokenResponse } from './types'

const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  /** Seconds from the Retry-After header, when the server sent one. */
  readonly retryAfter: number | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    retryAfter: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryAfter = retryAfter
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Send the bearer token and refresh it on 401. Defaults to true. */
  auth?: boolean
}

let sessionExpiredHandler: (() => void) | null = null

/** Called when the refresh token is rejected, so the app can return to the login page. */
export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = 'error'
  let message = `Request failed with status ${response.status}`
  let details: Record<string, unknown> = {}
  try {
    const body = (await response.json()) as {
      error?: { code?: unknown; message?: unknown; details?: unknown }
    } | null
    const error = body?.error
    if (error) {
      if (typeof error.code === 'string') code = error.code
      if (typeof error.message === 'string') message = error.message
      if (error.details && typeof error.details === 'object') {
        details = error.details as Record<string, unknown>
      }
    }
  } catch {
    // The body was not JSON; keep the generic error.
  }
  const retry = Number(response.headers.get('Retry-After'))
  return new ApiError(response.status, code, message, details, retry > 0 ? retry : null)
}

async function send(path: string, options: RequestOptions, token: string | null) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  try {
    return await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Network error')
  }
}

async function exchangeRefreshToken(refreshToken: string): Promise<boolean> {
  try {
    const response = await send(
      '/auth/refresh',
      { method: 'POST', body: { refresh_token: refreshToken } },
      null,
    )
    if (response.ok) {
      const tokens = (await response.json()) as TokenResponse
      setTokens(tokens.access_token, tokens.refresh_token)
      return true
    }
    // The server said the token is no good (not a temporary problem): forget it.
    if (response.status >= 400 && response.status < 500 && response.status !== 429) {
      clearTokens()
    }
  } catch {
    // Network trouble: keep the token so a later attempt can still succeed.
  }
  return false
}

let refreshInFlight: Promise<boolean> | null = null

/** Trade the refresh token for new tokens. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return Promise.resolve(false)
  refreshInFlight ??= exchangeRefreshToken(refreshToken).finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

/** Send a request with the bearer token, refreshing it once on 401. Throws ApiError on failure. */
async function sendAuthed(path: string, options: RequestOptions): Promise<Response> {
  const withAuth = options.auth !== false
  let response = await send(path, options, withAuth ? getAccessToken() : null)

  if (response.status === 401 && withAuth && getRefreshToken()) {
    if (await refreshSession()) {
      response = await send(path, options, getAccessToken())
    } else if (!getRefreshToken()) {
      sessionExpiredHandler?.()
    }
  }

  if (!response.ok) throw await toApiError(response)
  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await sendAuthed(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Fetch a file (such as a CSV report) with the bearer token. */
export async function requestFile(path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await sendAuthed(path, {})
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  return { blob: await response.blob(), filename: match?.[1] ?? 'report.csv' }
}
