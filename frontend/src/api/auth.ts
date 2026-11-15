import { request } from './http'
import type { AnyMe } from './types'

export function logoutRequest(refreshToken: string) {
  return request<void>('/auth/logout', {
    method: 'POST',
    body: { refresh_token: refreshToken },
    auth: false,
  })
}

export function forgotPasswordRequest(body: { email: string; user_type: 'person' }) {
  return request<{ status: string }>('/auth/forgot-password', {
    method: 'POST',
    body,
    auth: false,
  })
}

export function resetPasswordRequest(body: { token: string; new_password: string }) {
  return request<void>('/auth/reset-password', { method: 'POST', body, auth: false })
}

export function fetchMe() {
  return request<AnyMe>('/me')
}
