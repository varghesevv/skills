import { t } from '../../i18n'
import { fromLocalInput, toLocalInput } from '../../shared/dates'
import type { FieldErrors } from '../../shared/validation'

export type SortKey = 'newest' | 'rating' | 'rate'

export type FilterValues = {
  skills: string[]
  skillMatch: 'any' | 'all'
  skillLevel: string
  languages: string[]
  timings: string[]
  nativity: string[]
  maxRate: string
  currency: string
  negotiable: boolean
  availableFrom: string // value of a datetime-local input
  availableTo: string
  minRating: string
  orgId: string
  name: string
  sort: SortKey
}

export const EMPTY_FILTERS: FilterValues = {
  skills: [],
  skillMatch: 'any',
  skillLevel: '',
  languages: [],
  timings: [],
  nativity: [],
  maxRate: '',
  currency: '',
  negotiable: false,
  availableFrom: '',
  availableTo: '',
  minRating: '',
  orgId: '',
  name: '',
  sort: 'newest',
}

const SORTS: readonly SortKey[] = ['newest', 'rating', 'rate']

/** Read the filters back from the address bar, so a search can be shared and survives reloads. */
export function valuesFromParams(params: URLSearchParams): FilterValues {
  const sort = params.get('sort')
  const from = params.get('available_from')
  const to = params.get('available_to')
  return {
    skills: params.getAll('skill'),
    skillMatch: params.get('skill_match') === 'all' ? 'all' : 'any',
    skillLevel: params.get('skill_level') ?? '',
    languages: params.getAll('language'),
    timings: params.getAll('timing'),
    nativity: params.getAll('nativity'),
    maxRate: params.get('max_rate') ?? '',
    currency: params.get('currency') ?? '',
    negotiable: params.get('negotiable') === 'true',
    availableFrom: from ? toLocalInput(from) : '',
    availableTo: to ? toLocalInput(to) : '',
    minRating: params.get('min_rating') ?? '',
    orgId: params.get('org_id') ?? '',
    name: params.get('name') ?? '',
    sort: SORTS.find((key) => key === sort) ?? 'newest',
  }
}

/** Only non-default filters are written, which keeps addresses short. */
export function paramsFromValues(values: FilterValues): URLSearchParams {
  const params = new URLSearchParams()
  for (const skill of values.skills) params.append('skill', skill)
  if (values.skills.length > 1 && values.skillMatch === 'all') params.set('skill_match', 'all')
  if (values.skillLevel) params.set('skill_level', values.skillLevel)
  for (const language of values.languages) params.append('language', language)
  for (const timing of values.timings) params.append('timing', timing)
  for (const nativity of values.nativity) params.append('nativity', nativity)
  if (values.maxRate.trim()) params.set('max_rate', values.maxRate.trim())
  if (values.currency.trim()) params.set('currency', values.currency.trim().toUpperCase())
  if (values.negotiable) params.set('negotiable', 'true')
  const from = fromLocalInput(values.availableFrom)
  const to = fromLocalInput(values.availableTo)
  if (from) params.set('available_from', from)
  if (to) params.set('available_to', to)
  if (values.minRating) params.set('min_rating', values.minRating)
  if (values.orgId) params.set('org_id', values.orgId)
  if (values.name.trim()) params.set('name', values.name.trim())
  if (values.sort !== 'newest') params.set('sort', values.sort)
  return params
}

/** The same rules the API enforces, so the person hears about them before searching. */
export function validateFilters(values: FilterValues): FieldErrors {
  const errors: FieldErrors = {}
  const hasRate = values.maxRate.trim() !== ''
  if (hasRate && !/^\d{1,8}(\.\d{1,2})?$/.test(values.maxRate.trim())) {
    errors.maxRate = t('validation.rate')
  }
  const currency = values.currency.trim()
  if (currency !== '' && !/^[A-Za-z]{3}$/.test(currency)) errors.currency = t('validation.currency')
  if (hasRate && currency === '' && !errors.maxRate) errors.currency = t('search.needCurrency')
  const from = fromLocalInput(values.availableFrom)
  const to = fromLocalInput(values.availableTo)
  if ((values.availableFrom === '') !== (values.availableTo === '')) {
    const missing = values.availableFrom === '' ? 'availableFrom' : 'availableTo'
    errors[missing] = t('search.needBothDates')
  } else if (from && to && new Date(from) >= new Date(to)) {
    errors.availableTo = t('validation.periodOrder')
  }
  return errors
}

/** The query string sent to the API for one page of results. */
export function apiQuery(params: URLSearchParams, page: number, pageSize: number): string {
  const query = new URLSearchParams(params)
  query.set('page', String(page))
  query.set('page_size', String(pageSize))
  return query.toString()
}

export function pageFromParams(params: URLSearchParams): number {
  const page = Number.parseInt(params.get('page') ?? '1', 10)
  return Number.isNaN(page) || page < 1 ? 1 : page
}

export function activeFilterCount(values: FilterValues): number {
  const singles = [
    values.skillLevel,
    values.maxRate,
    values.negotiable,
    values.availableFrom,
    values.minRating,
    values.orgId,
    values.name.trim(),
    values.maxRate ? '' : values.currency.trim(),
  ].filter(Boolean).length
  return (
    values.skills.length +
    values.languages.length +
    values.timings.length +
    values.nativity.length +
    singles
  )
}
