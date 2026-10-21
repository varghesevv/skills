import { z } from 'zod'

import { t, type StringKey } from '../i18n'

// These rules mirror backend/app/schemas/auth.py. The server stays the authority; the client
// only saves a round trip. Field names match the API so server field errors line up.

export const MIN_PASSWORD_LENGTH = 10
export const MAX_PASSWORD_LENGTH = 128

const userType = z.enum(['freelancer', 'workhost', 'organisation', 'admin'])

const email = z
  .string()
  .trim()
  .min(1, 'validation.required')
  .max(254, 'validation.email')
  .email('validation.email')

const mobile = z
  .string()
  .transform((value) => value.replace(/[ -]/g, ''))
  .pipe(z.string().regex(/^\+?[0-9]{7,15}$/, 'validation.mobile'))

const newPassword = z
  .string()
  .min(MIN_PASSWORD_LENGTH, 'validation.passwordShort')
  .max(MAX_PASSWORD_LENGTH, 'validation.passwordLong')

const optionalText = z.string().trim().max(100, 'validation.tooLong')

export const loginSchema = z.object({
  email,
  password: z.string().min(1, 'validation.required').max(1024, 'validation.tooLong'),
  user_type: userType,
})

const registerBase = { email, mobile_number: mobile, password: newPassword }

export const freelancerRegisterSchema = z.object({
  ...registerBase,
  nationality: optionalText,
  primary_language: optionalText,
  whatsapp_availability: z.boolean(),
})

export const workhostRegisterSchema = z.object(registerBase)

export const organisationRegisterSchema = z.object({
  ...registerBase,
  org_name: z.string().trim().min(2, 'validation.orgName').max(200, 'validation.orgName'),
})

export const forgotPasswordSchema = z.object({ email, user_type: userType })

export const resetPasswordSchema = z.object({ new_password: newPassword })

export type FieldErrors = Record<string, string>

export type ValidationResult<T> = { ok: true; data: T } | { ok: false; errors: FieldErrors }

/** Run a schema and return translated messages keyed by field name. */
export function validate<S extends z.ZodTypeAny>(
  schema: S,
  values: unknown,
): ValidationResult<z.output<S>> {
  const result = schema.safeParse(values)
  if (result.success) return { ok: true, data: result.data as z.output<S> }
  const errors: FieldErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path.join('.')
    if (!(field in errors)) errors[field] = t(issue.message as StringKey)
  }
  return { ok: false, errors }
}
