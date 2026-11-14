import { request } from './http'
import type {
  AdmitResult,
  AdminInvitationInfo,
  AppliedStatus,
  ApplicantRow,
  FlaggedRow,
  GroupRequest,
  GroupRequestCreated,
  ChurchInvitation,
  ChurchInvitationCreated,
  ChurchSummary,
  HomeGroupSummary,
  IdName,
  InvitationInfo,
  MoveRequest,
  OwnerChurch,
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

/** The token travels in the body, never in the address. */
export function lookupAdminInvitation(token: string) {
  return request<AdminInvitationInfo>('/admin-invitations/lookup', {
    method: 'POST',
    body: { token },
    auth: false,
  })
}

export function acceptAdminInvitation(body: {
  token: string
  full_name: string
  mobile_number: string
  password: string
  home_group_name: string
}) {
  return request<{ id: string; church_id: string; status: string }>('/admin-invitations/accept', {
    method: 'POST',
    body,
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

export function fetchMembers(
  page: number,
  status?: Exclude<PersonStatus, 'pending' | 'revoked'>,
  homeGroupId?: string,
) {
  return request<Paged<MemberRow>>(
    `/verifier/members?${paging(page)}${status ? `&status=${status}` : ''}${homeGroupId ? `&home_group_id=${homeGroupId}` : ''}`,
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

/** Revoke someone below you. A VERIFIER's group gets `successorId` as its leader in the same step
 *  (without one it closes, if they are alone in it). */
export function revokePerson(id: string, successorId?: string) {
  return request<StatusResult>(`/verifier/people/${id}/status`, {
    method: 'PUT',
    body: { to: 'revoked', ...(successorId ? { successor_id: successorId } : {}) },
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

export function fetchGroupRequests(page: number) {
  return request<Paged<GroupRequest>>(`/group-requests?${paging(page)}`)
}

/** An ADMIN or the OWNER start the group at once; for anyone else this is a request. */
export function askForGroup(groupName: string, successorId?: string) {
  return request<GroupRequestCreated>('/group-requests', {
    method: 'POST',
    body: { group_name: groupName, ...(successorId ? { successor_id: successorId } : {}) },
  })
}

export function approveGroupRequest(id: string, successorId?: string) {
  return request<{ group: IdName }>(`/group-requests/${id}/approve`, {
    method: 'POST',
    body: successorId ? { successor_id: successorId } : {},
  })
}

export function declineGroupRequest(id: string) {
  return request<void>(`/group-requests/${id}/decline`, { method: 'POST' })
}

export function fetchMoves(page: number) {
  return request<Paged<MoveRequest>>(`/move-requests?${paging(page)}`)
}

/** Asking is the member's own agreement; the leaders of both groups must agree too. */
export function askToMove(homeGroupId: string) {
  return request<MoveRequest>('/move-requests', {
    method: 'POST',
    body: { home_group_id: homeGroupId },
  })
}

export function agreeToMove(id: string) {
  return request<MoveRequest>(`/move-requests/${id}/agree`, { method: 'POST' })
}

export function cancelMove(id: string) {
  return request<MoveRequest>(`/move-requests/${id}/cancel`, { method: 'POST' })
}

// ---- the OWNER's churches ----

export function fetchOwnerChurches(page: number) {
  return request<Paged<OwnerChurch>>(`/owner/churches?${paging(page)}`)
}

/** The link token is in the answer once; only its hash is kept. */
export function inviteAdmin(churchName: string, email: string) {
  return request<ChurchInvitationCreated>('/owner/churches', {
    method: 'POST',
    body: { church_name: churchName, email },
  })
}

export function fetchChurchInvitations(page: number) {
  return request<Paged<ChurchInvitation>>(`/owner/churches/invitations?${paging(page)}`)
}

export function cancelChurchInvitation(id: string) {
  return request<void>(`/owner/churches/invitations/${id}`, { method: 'DELETE' })
}

/** Closes the church, its groups and its members' accounts together; kept for the history. */
export function closeChurch(id: string) {
  return request<{ id: string; name: string; closed_groups: number; closed_accounts: number }>(
    `/owner/churches/${id}/close`,
    { method: 'POST' },
  )
}

export type FormerLeaderStatus = 'provider' | 'searcher' | 'keep'

/** Replace the leader of a group, or hand on one's own, with a member of it. */
export function replaceLeader(
  groupId: string,
  successorId: string,
  formerLeaderStatus: FormerLeaderStatus,
) {
  return request<{ group: { id: string; name: string }; leader: { id: string; name: string } }>(
    `/home-groups/${groupId}/leader`,
    {
      method: 'PUT',
      body: { successor_id: successorId, former_leader_status: formerLeaderStatus },
    },
  )
}

/** The leader closes their own group, being its last member, by joining another one. */
export function closeGroup(
  groupId: string,
  moveToGroupId: string,
  formerLeaderStatus: FormerLeaderStatus,
) {
  return request<{
    closed_group: { id: string; name: string }
    joined_group: { id: string; name: string }
    status: PersonStatus
  }>(`/home-groups/${groupId}/close`, {
    method: 'POST',
    body: { move_to_group_id: moveToGroupId, former_leader_status: formerLeaderStatus },
  })
}

/** An ADMIN or the OWNER move an admitted member to another open group of the church. */
export function movePerson(id: string, homeGroupId: string) {
  return request<{
    person: { id: string; name: string }
    home_group: { id: string; name: string }
  }>(`/verifier/people/${id}/move`, { method: 'POST', body: { home_group_id: homeGroupId } })
}

/** A searcher asks to become a provider; they stay a searcher while they collect vouches. */
export function applyForProvider() {
  return request<PersonMe>('/me/apply-provider', { method: 'POST' })
}
