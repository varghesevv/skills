import { request } from './http'
import type { AnyMe, TokenResponse } from './types'

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

/** The signed-in person chooses a new password; every other session ends, these tokens are new. */
export function changePasswordRequest(body: { current_password: string; new_password: string }) {
  return request<TokenResponse>('/auth/change-password', { method: 'POST', body })
}
