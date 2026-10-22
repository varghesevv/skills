// Shapes of the API responses used by the shell. Keep in step with docs/specification/04-api.md.

export type UserType = 'freelancer' | 'workhost' | 'organisation' | 'admin'
export type RegisterType = Exclude<UserType, 'admin'>

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
  mobile_number: string | null
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
