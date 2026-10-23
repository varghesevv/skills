import type { OrgBrief } from '../../api/types'
import { t } from '../../i18n'
import { formatDateTime, fromLocalInput } from '../../shared/dates'
import { EMPTY_FILTERS, type FilterValues } from './searchParams'

export type FilterChip = {
  key: string
  label: string
  /** The filters left after this one is removed. */
  without: (values: FilterValues) => FilterValues
}

function dateText(local: string): string {
  const iso = fromLocalInput(local)
  return iso ? formatDateTime(iso) : local
}

/** One chip per applied filter, so a single filter can be removed without opening the panel. */
export function activeChips(values: FilterValues, organisations: OrgBrief[]): FilterChip[] {
  const chips: FilterChip[] = []
  const drop =
    (name: 'skills' | 'languages' | 'timings' | 'nativity', value: string) =>
    (current: FilterValues): FilterValues => ({
      ...current,
      [name]: current[name].filter((item) => item !== value),
    })

  if (values.name.trim()) {
    chips.push({
      key: 'name',
      label: t('search.chip.name', { name: values.name.trim() }),
      without: (current) => ({ ...current, name: '' }),
    })
  }
  for (const skill of values.skills) {
    chips.push({ key: `skill:${skill}`, label: skill, without: drop('skills', skill) })
  }
  if (values.skillLevel) {
    chips.push({
      key: 'level',
      label: t('search.chip.level', { level: values.skillLevel }),
      without: (current) => ({ ...current, skillLevel: '' }),
    })
  }
  for (const [name, list] of [
    ['languages', values.languages],
    ['timings', values.timings],
    ['nativity', values.nativity],
  ] as const) {
    for (const item of list)
      chips.push({ key: `${name}:${item}`, label: item, without: drop(name, item) })
  }
  if (values.maxRate) {
    chips.push({
      key: 'rate',
      label: t('search.chip.maxRate', {
        rate: values.maxRate,
        currency: values.currency.trim().toUpperCase(),
      }),
      without: (current) => ({ ...current, maxRate: '', currency: '' }),
    })
  } else if (values.currency.trim()) {
    chips.push({
      key: 'currency',
      label: t('search.chip.currency', { currency: values.currency.trim().toUpperCase() }),
      without: (current) => ({ ...current, currency: '' }),
    })
  }
  if (values.negotiable) {
    chips.push({
      key: 'negotiable',
      label: t('search.negotiable'),
      without: (current) => ({ ...current, negotiable: false }),
    })
  }
  if (values.availableFrom && values.availableTo) {
    chips.push({
      key: 'available',
      label: t('search.chip.available', {
        from: dateText(values.availableFrom),
        to: dateText(values.availableTo),
      }),
      without: (current) => ({ ...current, availableFrom: '', availableTo: '' }),
    })
  }
  if (values.minRating) {
    chips.push({
      key: 'rating',
      label: t('search.ratingAtLeast', { rating: values.minRating }),
      without: (current) => ({ ...current, minRating: '' }),
    })
  }
  if (values.orgId) {
    const org = organisations.find((item) => item.id === values.orgId)
    chips.push({
      key: 'org',
      label: org ? t('search.chip.org', { name: org.org_name }) : t('search.chip.vouchedUnknown'),
      without: (current) => ({ ...current, orgId: '' }),
    })
  }
  return chips
}

/** Everything cleared except how the results are sorted. */
export function clearedFilters(values: FilterValues): FilterValues {
  return { ...EMPTY_FILTERS, sort: values.sort }
}
