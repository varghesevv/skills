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
