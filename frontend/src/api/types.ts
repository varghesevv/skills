// Shapes of the API responses used by the shell. Keep in step with docs/specification/04-api.md.

export type UserType = 'freelancer' | 'workhost' | 'organisation' | 'admin'
export type RegisterType = Exclude<UserType, 'admin'>
/** The identity of the church trust model; the four above are the older accounts. */
export type AuthUserType = UserType | 'person'

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export type Me = {
  id: string
  user_type: UserType
  email: string
  mobile_number: string
  full_name: string | null
  org_name: string | null
  approval_status: string | null
  created_at: string
}

export type PersonStatus =
  'revoked' | 'pending' | 'searcher' | 'provider' | 'verifier' | 'admin' | 'owner'
export type AppliedStatus = 'searcher' | 'provider'
export type IdName = { id: string; name: string }

/** GET /me for a person of the church trust model (docs/specification/04-api.md). */
export type PersonMe = {
  user_type: 'person'
  id: string
  full_name: string
  email: string
  mobile_number: string
  status: PersonStatus
  requested_status: AppliedStatus | null
  church: IdName
  home_group: IdName | null
  leader: { name: string } | null
  status_set_by: { name: string } | null
  flagged_for_recheck: boolean
  vouch_count: number
}

export type AnyMe = Me | PersonMe

// ---- vouching and notifications (docs/specification/04-api.md) ----

export type VouchLinkState = { active: boolean; expires_at: string | null }
export type VouchLinkCreated = { token: string; expires_at: string }
export type VouchLinkInfo = {
  applicant_name: string
  church_name: string
  home_group_name: string
  requested_status: AppliedStatus
  already_vouched: boolean
}
export type VouchReceived = {
  id: string
  voucher_name: string
  church_name: string
  live: boolean
  created_at: string
}
export type VouchGiven = {
  id: string
  applicant_name: string
  applicant_status: string
  requested_status: string | null
  withdrawn: boolean
  can_withdraw: boolean
  created_at: string
}
export type NotificationItem = {
  id: string
  kind: string
  subject: IdName | null
  created_at: string
  read: boolean
}
export type NotificationList = { items: NotificationItem[]; total: number; unread_count: number }

export type ChurchSummary = { id: string; name: string }
export type HomeGroupSummary = { id: string; name: string; leader_name: string }
export type InvitationInfo = { church_name: string; home_group_name: string; leader_name: string }

export type SignupBody = {
  full_name: string
  email: string
  mobile_number: string
  password: string
  requested_status: AppliedStatus
  home_group_id?: string
  invitation_token?: string
}

export type RegisterResponse = {
  id: string
  user_type: UserType
  email: string
  approval_status: string | null
}

// ---- freelancer portal (docs/specification/04-api.md) ----

export type Page<T> = { items: T[]; total: number; page: number; page_size: number }

export type LabelType = 'skill' | 'language' | 'timing' | 'nativity' | 'skill_level'

export type LabelOut = {
  id: string
  label_name: string
  label_type: LabelType
  is_active: boolean
}

export type FreelancerLabel = { label: LabelOut; level: LabelOut | null }

export type FreelancerProfile = {
  id: string
  full_name: string | null
  email: string
  mobile_number: string
  whatsapp_availability: boolean
  nationality: string | null
  primary_language: string | null
  rate_per_hour: number | null
  rate_currency: string | null
  is_rate_negotiable: boolean
  labels: FreelancerLabel[]
  created_at: string
}

export type ProfileUpdate = {
  full_name: string
  mobile_number: string
  whatsapp_availability: boolean
  nationality: string | null
  primary_language: string | null
  rate_per_hour: number | null
  rate_currency: string | null
  is_rate_negotiable: boolean
}

export type LabelSelection = { label_id: string; level_label_id: string | null }

export type Unavailability = { id: string; unavailable_from: string; unavailable_to: string }

export type VouchStatus = 'pending' | 'approved' | 'revoked'

export type Vouch = {
  org_id: string
  org_name: string
  status: VouchStatus
  is_active: boolean
  created_at: string
}

export type PublicRating = { rating: number; comment: string | null; rated_on: string }

// ---- work host portal ----

export type Day = 'sun' | 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat'
export const DAYS: readonly Day[] = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']

export type WorkHostProfile = {
  id: string
  full_name: string | null
  email: string
  mobile_number: string
  available_days: Day[]
  created_at: string
}

export type WorkHostUpdate = {
  full_name: string
  mobile_number: string
  available_days: Day[]
}

export type SearchResult = {
  id: string
  full_name: string | null
  nationality: string | null
  primary_language: string | null
  whatsapp_availability: boolean
  rate_per_hour: number | null
  rate_currency: string | null
  is_rate_negotiable: boolean
  average_rating: number | null
  rating_count: number
  vouch_count: number
  skills: { name: string; level: string | null }[]
  languages: string[]
  timings: string[]
  nativity: string[]
}

export type GivenRating = {
  id: string
  freelancer_id: string
  freelancer_name: string | null
  rating: number
  comment: string | null
  rated_on: string
  updated_at: string | null
}

export type FreelancerPublic = {
  id: string
  full_name: string | null
  whatsapp_availability: boolean
  nationality: string | null
  primary_language: string | null
  rate_per_hour: number | null
  rate_currency: string | null
  is_rate_negotiable: boolean
  labels: FreelancerLabel[]
  average_rating: number | null
  rating_count: number
  vouched_by: { org_id: string; org_name: string }[]
  unavailable: Unavailability[]
  my_rating: GivenRating | null
}

export type RevealRequest = {
  channel: 'dial' | 'show'
  source: 'search' | 'detail'
  searched_skills: string[]
}

export type RevealedMobile = { mobile_number: string }

export type OrgBrief = { id: string; org_name: string }

// ---- organisation portal ----

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export type OrgProfile = {
  id: string
  email: string
  org_name: string
  mobile_number: string
  approval_status: ApprovalStatus
  created_at: string
}

export type OrgUpdate = { org_name: string; mobile_number: string }

export type VouchedFreelancer = {
  freelancer_id: string
  full_name: string | null
  nationality: string | null
  primary_language: string | null
  status: VouchStatus
  is_active: boolean
  created_at: string
}

export type ReportInfo = {
  name: string
  code: string
  title: string
  description: string
  filters: string[]
}

export type ReportCell = string | number | boolean | null

export type ReportData = {
  name: string
  title: string
  window: { from: string; to: string }
  row_count: number
  sections: { title: string; columns: string[]; rows: ReportCell[][] }[]
}

// ---- admin portal ----

export type OrgSummary = {
  id: string
  org_name: string
  email: string
  mobile_number: string
  approval_status: ApprovalStatus
  created_at: string
}

export type ReportRun = {
  id: string
  report_name: string
  window_from: string
  window_to: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'succeeded' | 'failed'
  row_count: number | null
  error_message: string | null
  has_files: boolean
}

export type ReportSchedule = {
  report_name: string
  cron_expression: string
  timezone: string
  is_enabled: boolean
}

// ---- the screens of a leader (docs/specification/04-api.md, "Verifier") ----

export type Voucher = { name: string; church_name: string; live: boolean }
export type ApplicantRow = {
  id: string
  full_name: string
  /** pending, or searcher for a member who asks to become a provider */
  status: PersonStatus
  requested_status: AppliedStatus | null
  home_group: IdName
  applied_at: string
  vouch_count: number
  vouchers: Voucher[]
  /** The server's answer: may the caller admit this person as a provider now? */
  can_admit_as_provider: boolean
}
export type MemberRow = {
  id: string
  full_name: string
  status: PersonStatus
  home_group: IdName | null
  status_set_by: { name: string } | null
  flagged_for_recheck: boolean
}
export type RevokedRow = {
  id: string
  full_name: string
  removed_from: IdName | null
  revoked_by: { name: string } | null
  revoked_at: string | null
}
export type FlaggedRow = {
  id: string
  full_name: string
  status: PersonStatus
  home_group: IdName | null
  status_set_by: { name: string } | null
}
export type StatusResult = {
  id: string
  status: PersonStatus
  home_group_id: string | null
  flagged_for_recheck: boolean
}
export type GroupRequest = {
  id: string
  group_name: string
  church: IdName
  requester: IdName
  state: 'open' | 'approved' | 'declined'
  created_at: string
  /** Approving needs someone to lead the group the requester leads now. */
  requester_leads_a_group: boolean
  /** The open group the requester belongs to now: whose members may lead it instead. */
  requester_group: IdName | null
}
export type GroupRequestCreated = { request: GroupRequest; group: IdName | null }
export type MoveRequest = {
  id: string
  person: IdName
  from_group: IdName
  to_group: IdName
  agreed: { person: boolean; from_leader: boolean; to_leader: boolean }
  state: 'open' | 'completed' | 'cancelled'
  created_at: string
}
export type Paged<T> = { items: T[]; total: number }
export type HistoryEntry = {
  kind: string
  from_status: string | null
  to_status: string
  changed_by: { name: string } | null
  at: string
}
export type ChainLink = { id: string; full_name: string; status: PersonStatus }
export type PersonDetail = {
  id: string
  full_name: string
  mobile_number: string
  status: PersonStatus
  requested_status: AppliedStatus | null
  church: IdName
  home_group: IdName | null
  status_set_by: { name: string } | null
  flagged_for_recheck: boolean
  applied_at: string
  history: HistoryEntry[]
  chain_of_trust: ChainLink[]
  vouches: Voucher[]
  can_admit_as_provider: boolean
}
export type AdmitResult = {
  id: string
  status: PersonStatus
  requested_status: AppliedStatus | null
}
