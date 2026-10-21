import { describe, expect, it, vi } from 'vitest'

import { clearTokens, getRefreshToken, setTokens } from '../auth/tokenStore'
import { apiError, json, mockApi, tokens } from '../testUtils'
import { ApiError, onSessionExpired, request } from './http'

describe('request', () => {
  it('sends the access token as a bearer token', async () => {
    setTokens('access-1', 'refresh-1')
    const api = mockApi({ 'GET /me': () => json(200, { ok: true }) })
    await request('/me')
    expect(api.last('GET /me')?.headers.get('Authorization')).toBe('Bearer access-1')
  })

  it('returns undefined for 204 responses', async () => {
    const api = mockApi({ 'POST /auth/logout': () => json(204) })
    expect(await request('/auth/logout', { method: 'POST', body: {}, auth: false })).toBeUndefined()
    expect(api.last('POST /auth/logout')?.headers.get('Authorization')).toBeNull()
  })

  it('turns an error body into an ApiError, with Retry-After', async () => {
    mockApi({
      'POST /auth/login': () =>
        apiError(429, 'too_many_attempts', { a: 1 }, { 'Retry-After': '120' }),
    })
    const error = await request('/auth/login', { method: 'POST', body: {}, auth: false }).catch(
      (e: unknown) => e,
    )
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 429, code: 'too_many_attempts', retryAfter: 120 })
  })

  it('reports a network failure as network_error', async () => {
    mockApi({
      'GET /me': () => {
        throw new TypeError('offline')
      },
    })
    await expect(request('/me')).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('refreshes the tokens once on 401 and retries the request', async () => {
    setTokens('stale', 'refresh-1')
    const api = mockApi({
      'POST /auth/refresh': () => json(200, tokens('2')),
      'GET /me': ({ headers }) =>
        headers.get('Authorization') === 'Bearer access-2'
          ? json(200, { id: 'x' })
          : apiError(401, 'not_authenticated'),
    })
    expect(await request('/me')).toEqual({ id: 'x' })
    expect(api.count('POST /auth/refresh')).toBe(1)
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('shares one refresh between simultaneous requests', async () => {
    setTokens('stale', 'refresh-1')
    const api = mockApi({
      'POST /auth/refresh': () => json(200, tokens('2')),
      'GET /me': ({ headers }) =>
        headers.get('Authorization') === 'Bearer access-2'
          ? json(200, {})
          : apiError(401, 'not_authenticated'),
    })
    await Promise.all([request('/me'), request('/me'), request('/me')])
    expect(api.count('POST /auth/refresh')).toBe(1)
  })

  it('forgets the session and tells the app when the refresh token is rejected', async () => {
    setTokens('stale', 'refresh-1')
    const expired = vi.fn()
    onSessionExpired(expired)
    mockApi({
      'POST /auth/refresh': () => apiError(401, 'invalid_refresh_token'),
      'GET /me': () => apiError(401, 'not_authenticated'),
    })
    await expect(request('/me')).rejects.toMatchObject({ status: 401 })
    expect(getRefreshToken()).toBeNull()
    expect(expired).toHaveBeenCalledOnce()
  })

  it('keeps the refresh token when the refresh fails because of the network', async () => {
    setTokens('stale', 'refresh-1')
    const expired = vi.fn()
    onSessionExpired(expired)
    mockApi({
      'POST /auth/refresh': () => {
        throw new TypeError('offline')
      },
      'GET /me': () => apiError(401, 'not_authenticated'),
    })
    await expect(request('/me')).rejects.toMatchObject({ status: 401 })
    expect(getRefreshToken()).toBe('refresh-1')
    expect(expired).not.toHaveBeenCalled()
    clearTokens()
  })

  it('does not try to refresh when auth is off (a wrong password is a plain 401)', async () => {
    setTokens('a', 'refresh-1')
    const api = mockApi({ 'POST /auth/login': () => apiError(401, 'invalid_credentials') })
    await expect(
      request('/auth/login', { method: 'POST', body: {}, auth: false }),
    ).rejects.toMatchObject({ code: 'invalid_credentials' })
    expect(api.count('POST /auth/refresh')).toBe(0)
  })
})
