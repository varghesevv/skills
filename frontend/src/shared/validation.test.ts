import { describe, expect, it } from 'vitest'

import {
  acceptInvitationSchema,
  forgotPasswordSchema,
  personLoginSchema,
  resetPasswordSchema,
  signupDetailsSchema,
  validate,
} from './validation'

const base = {
  full_name: ' Amina Yusuf ',
  email: ' A@Example.com ',
  mobile_number: '+971 50-000 0001',
  password: 'x'.repeat(10),
}

describe('validate', () => {
  it('cleans up email and mobile number', () => {
    expect(validate(signupDetailsSchema, base)).toMatchObject({
      ok: true,
      data: { full_name: 'Amina Yusuf', email: 'A@Example.com', mobile_number: '+971500000001' },
    })
  })

  it('rejects a bad mobile number and a short password with readable messages', () => {
    const result = validate(acceptInvitationSchema, {
      ...base,
      mobile_number: 'call me',
      password: 'x'.repeat(9),
      home_group_name: 'A',
    })
    expect(result).toEqual({
      ok: false,
      errors: {
        mobile_number: 'Enter 7 to 15 digits, optionally starting with +.',
        password: 'Use at least 10 characters.',
        home_group_name: 'Enter 2 to 200 characters.',
      },
    })
  })

  it('requires a name', () => {
    expect(validate(signupDetailsSchema, { ...base, full_name: 'A' })).toMatchObject({
      ok: false,
      errors: { full_name: 'Enter your name (2 to 200 characters).' },
    })
    expect(validate(signupDetailsSchema, { ...base, full_name: '' }).ok).toBe(false)
  })

  it('requires a login password but does not length-check it', () => {
    expect(validate(personLoginSchema, { email: 'a@b.co', password: 'x' }).ok).toBe(true)
    expect(validate(personLoginSchema, { email: '', password: '' })).toMatchObject({
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
