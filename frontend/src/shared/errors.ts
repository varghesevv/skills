import { ApiError } from '../api/http'
import { t } from '../i18n'
import type { FieldErrors } from './validation'

/** A message safe to show a person. Never includes anything they typed. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case 'invalid_credentials':
        return t('error.invalidCredentials')
      case 'organisation_pending':
        return t('error.organisationPending')
      case 'organisation_rejected':
        return t('error.organisationRejected')
      case 'too_many_attempts':
        return t('error.tooManyAttempts', {
          minutes: Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60)),
        })
      case 'email_taken':
        return t('error.emailTaken')
      case 'invalid_reset_token':
        return t('error.invalidResetToken')
      case 'network_error':
        return t('error.network')
      case 'service_unavailable':
        return t('error.unavailable')
      case 'validation_error':
        return t('error.fixFields')
    }
  }
  return t('error.generic')
}

/** Field-level messages from a 422 response, keyed by API field name. */
export function serverFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError) || error.code !== 'validation_error') return {}
  const fields = error.details.fields
  if (!Array.isArray(fields)) return {}
  const result: FieldErrors = {}
  for (const item of fields as { field?: unknown; message?: unknown }[]) {
    if (
      typeof item.field === 'string' &&
      typeof item.message === 'string' &&
      !(item.field in result)
    ) {
      result[item.field] = item.message
    }
  }
  return result
}
