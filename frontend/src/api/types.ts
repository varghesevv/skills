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
