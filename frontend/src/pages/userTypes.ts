import type { UserType } from '../api/types'
import { t } from '../i18n'

export const USER_TYPE_OPTIONS = [
  { value: 'freelancer', label: t('role.freelancer') },
  { value: 'workhost', label: t('role.workhost') },
  { value: 'organisation', label: t('role.organisation') },
  { value: 'admin', label: t('role.admin') },
] as const

export function isUserType(value: string | null): value is UserType {
  return USER_TYPE_OPTIONS.some((option) => option.value === value)
}
