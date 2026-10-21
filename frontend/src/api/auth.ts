import { request } from './http'
import type { Me, RegisterResponse, RegisterType, TokenResponse, UserType } from './types'

export function loginRequest(body: { email: string; password: string; user_type: UserType }) {
  return request<TokenResponse>('/auth/login', { method: 'POST', body, auth: false })
}

export function registerRequest(type: RegisterType, body: Record<string, unknown>) {
  return request<RegisterResponse>(`/auth/register/${type}`, {
    method: 'POST',
    body,
    auth: false,
  })
}

export function logoutRequest(refreshToken: string) {
  return request<void>('/auth/logout', {
    method: 'POST',
    body: { refresh_token: refreshToken },
    auth: false,
  })
}

export function forgotPasswordRequest(body: { email: string; user_type: UserType }) {
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
  return request<Me>('/me')
}
