import { describe, expect, it } from 'vitest'

import {
  forgotPasswordSchema,
  freelancerRegisterSchema,
  loginSchema,
  organisationRegisterSchema,
  resetPasswordSchema,
  validate,
  workhostRegisterSchema,
} from './validation'

const base = {
  full_name: ' Amina Yusuf ',
  email: ' A@Example.com ',
  mobile_number: '+971 50-000 0001',
  password: 'x'.repeat(10),
}

describe('validate', () => {
  it('cleans up email and mobile number', () => {
    const result = validate(freelancerRegisterSchema, {
      ...base,
      nationality: ' UAE ',
      primary_language: '',
      whatsapp_availability: true,
    })
    expect(result).toMatchObject({
      ok: true,
      data: {
        full_name: 'Amina Yusuf',
        email: 'A@Example.com',
        mobile_number: '+971500000001',
        nationality: 'UAE',
      },
    })
  })

  it('rejects a bad mobile number and a short password with readable messages', () => {
    const result = validate(organisationRegisterSchema, {
      ...base,
      mobile_number: 'call me',
      password: 'x'.repeat(9),
      org_name: 'A',
    })
    expect(result).toEqual({
      ok: false,
      errors: {
        mobile_number: 'Enter 7 to 15 digits, optionally starting with +.',
        password: 'Use at least 10 characters.',
        org_name: 'Enter 2 to 200 characters.',
      },
    })
  })

  it('requires a name for people but not for organisations', () => {
    const noName = { ...base, full_name: 'A', nationality: '', whatsapp_availability: false }
    expect(validate(freelancerRegisterSchema, noName)).toMatchObject({
      ok: false,
      errors: { full_name: 'Enter your name (2 to 200 characters).' },
    })
    expect(validate(workhostRegisterSchema, { ...base, full_name: '' }).ok).toBe(false)
    expect(validate(organisationRegisterSchema, { ...base, org_name: 'Acme' }).ok).toBe(true)
  })

  it('requires a login password but does not length-check it', () => {
    expect(validate(loginSchema, { email: 'a@b.co', password: 'x', user_type: 'admin' }).ok).toBe(
      true,
    )
    expect(validate(loginSchema, { email: '', password: '', user_type: 'admin' })).toMatchObject({
      ok: false,
      errors: { email: 'This field is required.', password: 'This field is required.' },
    })
  })

  it('checks the forgot and reset forms', () => {
    expect(validate(forgotPasswordSchema, { email: 'nope', user_type: 'workhost' }).ok).toBe(false)
    expect(validate(resetPasswordSchema, { new_password: 'short' }).ok).toBe(false)
    expect(validate(resetPasswordSchema, { new_password: 'x'.repeat(129) }).ok).toBe(false)
  })
})
