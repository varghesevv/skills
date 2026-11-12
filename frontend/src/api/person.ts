import { request } from './http'
import type {
  AppliedStatus,
  ChurchSummary,
  HomeGroupSummary,
  InvitationInfo,
  PersonMe,
  SignupBody,
  TokenResponse,
} from './types'

/** One login for every person: no account type is sent (the server's default is the person). */
export function personLoginRequest(body: { email: string; password: string }) {
  return request<TokenResponse>('/auth/login', { method: 'POST', body, auth: false })
}

export function signupRequest(body: SignupBody) {
  return request<{ id: string; status: 'pending' }>('/auth/signup', {
    method: 'POST',
    body,
    auth: false,
  })
}

export function fetchChurches() {
  return request<{ items: ChurchSummary[] }>('/churches', { auth: false })
}

export function fetchHomeGroups(churchId: string) {
  return request<{ items: HomeGroupSummary[] }>(`/churches/${churchId}/home-groups`, {
    auth: false,
  })
}

/** The token travels in the body, never in the address. */
export function lookupInvitation(token: string) {
  return request<InvitationInfo>('/group-invitations/lookup', {
    method: 'POST',
    body: { token },
    auth: false,
  })
}

export function updateApplication(body: {
  home_group_id?: string
  requested_status?: AppliedStatus
}) {
  return request<PersonMe>('/me/application', { method: 'PUT', body })
}

export function closeAccount(password: string) {
  return request<void>('/me', { method: 'DELETE', body: { password } })
}
