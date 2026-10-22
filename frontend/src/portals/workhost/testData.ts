import type { FreelancerPublic, SearchResult } from '../../api/types'

export const PERSON_ID = '22222222-2222-2222-2222-222222222222'

export function makeResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    id: PERSON_ID,
    full_name: 'Anita Sharma',
    nationality: 'Indian',
    primary_language: 'Hindi',
    whatsapp_availability: true,
    rate_per_hour: 50,
    rate_currency: 'AED',
    is_rate_negotiable: true,
    average_rating: 8.5,
    rating_count: 4,
    vouch_count: 2,
    skills: [{ name: 'plumbing', level: '80%' }],
    languages: ['English'],
    timings: ['weekends'],
    nativity: [],
    ...overrides,
  }
}

export function makePerson(overrides: Partial<FreelancerPublic> = {}): FreelancerPublic {
  return {
    id: PERSON_ID,
    full_name: 'Anita Sharma',
    mobile_number: '+971500000011',
    whatsapp_availability: true,
    nationality: 'Indian',
    primary_language: 'Hindi',
    rate_per_hour: 50,
    rate_currency: 'AED',
    is_rate_negotiable: true,
    labels: [
      {
        label: { id: 'sk1', label_name: 'plumbing', label_type: 'skill', is_active: true },
        level: { id: 'lv3', label_name: '80%', label_type: 'skill_level', is_active: true },
      },
      {
        label: { id: 'lg1', label_name: 'English', label_type: 'language', is_active: true },
        level: null,
      },
    ],
    average_rating: 8.5,
    rating_count: 4,
    vouched_by: [{ org_id: 'o1', org_name: 'Acme Training' }],
    unavailable: [
      {
        id: 'u1',
        unavailable_from: '2026-12-10T08:00:00Z',
        unavailable_to: '2026-12-12T20:00:00Z',
      },
    ],
    my_rating: null,
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length, pageNumber = 1) => ({
  items,
  total,
  page: pageNumber,
  page_size: 12,
})
