import type { FreelancerProfile, LabelOut } from '../../api/types'

export const ME_ID = '11111111-1111-1111-1111-111111111111'

export function label(
  id: string,
  label_name: string,
  label_type: LabelOut['label_type'],
): LabelOut {
  return { id, label_name, label_type, is_active: true }
}

export const PLUMBING = label('sk1', 'plumbing', 'skill')
export const CARPENTRY = label('sk2', 'carpentry', 'skill')
export const BASIC = label('lv1', 'basic', 'skill_level')
export const HALF = label('lv2', '50%', 'skill_level')
export const EIGHTY = label('lv3', '80%', 'skill_level')
export const ENGLISH = label('lg1', 'English', 'language')
export const WEEKENDS = label('tm1', 'weekends', 'timing')

export const ALL_LABELS: LabelOut[] = [PLUMBING, CARPENTRY, BASIC, HALF, EIGHTY, ENGLISH, WEEKENDS]

export function makeProfile(overrides: Partial<FreelancerProfile> = {}): FreelancerProfile {
  return {
    id: ME_ID,
    full_name: 'Fatima Khan',
    email: 'f@example.com',
    mobile_number: '+971500000001',
    whatsapp_availability: false,
    nationality: 'Indian',
    primary_language: null,
    rate_per_hour: null,
    rate_currency: null,
    is_rate_negotiable: false,
    labels: [],
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}
