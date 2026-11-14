import { request } from './http'
import type {
  AdmitResult,
  AppliedStatus,
  ApplicantRow,
  FlaggedRow,
  ChurchSummary,
  HomeGroupSummary,
  InvitationInfo,
  MemberRow,
  RevokedRow,
  StatusResult,
  NotificationList,
  Paged,
  PersonDetail,
  PersonMe,
  PersonStatus,
  SignupBody,
  TokenResponse,
  VouchGiven,
  VouchLinkCreated,
  VouchLinkInfo,
  VouchLinkState,
  VouchReceived,
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

export function fetchVouchLinkState() {
  return request<VouchLinkState>('/me/vouch-link')
}

/** The link is shown once: only a hash is kept, and a new link ends the one before it. */
export function makeVouchLink() {
  return request<VouchLinkCreated>('/me/vouch-link', { method: 'POST' })
}

export function fetchVouchesReceived() {
  return request<{ items: VouchReceived[] }>('/me/vouches')
}

export function fetchVouchesGiven() {
  return request<{ items: VouchGiven[] }>('/me/vouches-given')
}

/** The token travels in the body, never in the address. */
export function lookupVouchLink(token: string) {
  return request<VouchLinkInfo>('/vouch-links/lookup', { method: 'POST', body: { token } })
}

export function vouchThroughLink(token: string) {
  return request<{ id: string }>('/vouch-links/vouch', { method: 'POST', body: { token } })
}

export function withdrawVouch(id: string) {
  return request<void>(`/vouches/${id}`, { method: 'DELETE' })
}

export function fetchNotifications() {
  return request<NotificationList>('/me/notifications?limit=50')
}

export function markNotificationRead(id: string) {
  return request<void>(`/me/notifications/${id}/read`, { method: 'POST' })
}

export function markAllNotificationsRead() {
  return request<void>('/me/notifications/read-all', { method: 'POST' })
}

// ---- the screens of a leader ----

export const LEADER_PAGE_SIZE = 50

const paging = (page: number) => `limit=${LEADER_PAGE_SIZE}&offset=${(page - 1) * LEADER_PAGE_SIZE}`

export function fetchApplicants(page: number) {
  return request<Paged<ApplicantRow>>(`/verifier/applicants?${paging(page)}`)
}

export function fetchMembers(page: number, status?: Exclude<PersonStatus, 'pending' | 'revoked'>) {
  return request<Paged<MemberRow>>(
    `/verifier/members?${paging(page)}${status ? `&status=${status}` : ''}`,
  )
}

/** The only response with a mobile number besides the reveal: each call is logged. */
export function fetchPersonDetail(id: string) {
  return request<PersonDetail>(`/verifier/people/${id}`)
}

export function admitPerson(id: string, to: AppliedStatus) {
  return request<AdmitResult>(`/verifier/people/${id}/admit`, { method: 'POST', body: { to } })
}

export function declinePerson(id: string) {
  return request<void>(`/verifier/people/${id}/decline`, { method: 'POST' })
}

export function fetchRevoked(page: number) {
  return request<Paged<RevokedRow>>(`/verifier/revoked?${paging(page)}`)
}

export function fetchFlagged(page: number) {
  return request<Paged<FlaggedRow>>(`/verifier/flagged?${paging(page)}`)
}

/** Revoke someone below you. A leader needs a successor first, which is for the ADMIN screens. */
export function revokePerson(id: string) {
  return request<StatusResult>(`/verifier/people/${id}/status`, {
    method: 'PUT',
    body: { to: 'revoked' },
  })
}

/** Bring a revoked person back into a home group of their church. */
export function reinstatePerson(id: string, to: 'searcher' | 'provider', homeGroupId: string) {
  return request<StatusResult>(`/verifier/people/${id}/status`, {
    method: 'PUT',
    body: { to, home_group_id: homeGroupId },
  })
}

/** Clear a re-check flag: the caller becomes the new link in the person's chain of trust. */
export function reconfirmPerson(id: string) {
  return request<StatusResult>(`/verifier/people/${id}/reconfirm`, { method: 'POST' })
}

/** A searcher asks to become a provider; they stay a searcher while they collect vouches. */
export function applyForProvider() {
  return request<PersonMe>('/me/apply-provider', { method: 'POST' })
}
