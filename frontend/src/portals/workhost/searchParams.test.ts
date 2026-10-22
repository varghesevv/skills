import { describe, expect, it } from 'vitest'

import {
  EMPTY_FILTERS,
  activeFilterCount,
  apiQuery,
  pageFromParams,
  paramsFromValues,
  validateFilters,
  valuesFromParams,
} from './searchParams'

describe('search parameters', () => {
  it('writes only what differs from the defaults', () => {
    expect(paramsFromValues(EMPTY_FILTERS).toString()).toBe('')
    const params = paramsFromValues({
      ...EMPTY_FILTERS,
      skills: ['plumbing', 'carpentry'],
      skillMatch: 'all',
      skillLevel: '50%',
      maxRate: '60',
      currency: 'aed',
      negotiable: true,
      minRating: '7',
      sort: 'rate',
    })
    expect(params.getAll('skill')).toEqual(['plumbing', 'carpentry'])
    expect(params.get('skill_match')).toBe('all')
    expect(params.get('skill_level')).toBe('50%')
    expect(params.get('currency')).toBe('AED')
    expect(params.get('negotiable')).toBe('true')
    expect(params.get('sort')).toBe('rate')
  })

  it('does not send skill_match=all for a single skill', () => {
    const params = paramsFromValues({ ...EMPTY_FILTERS, skills: ['plumbing'], skillMatch: 'all' })
    expect(params.has('skill_match')).toBe(false)
  })

  it('round-trips through the address bar, including dates', () => {
    const values = {
      ...EMPTY_FILTERS,
      languages: ['English'],
      timings: ['weekends'],
      availableFrom: '2026-12-01T09:00',
      availableTo: '2026-12-03T18:00',
    }
    const again = valuesFromParams(new URLSearchParams(paramsFromValues(values).toString()))
    expect(again).toEqual(values)
  })

  it('ignores a sort it does not know', () => {
    expect(valuesFromParams(new URLSearchParams('sort=oldest')).sort).toBe('newest')
  })

  it('checks the same rules as the API', () => {
    expect(validateFilters({ ...EMPTY_FILTERS, maxRate: '50' })).toHaveProperty('currency')
    const badRate = validateFilters({ ...EMPTY_FILTERS, maxRate: 'abc', currency: 'AED' })
    expect(badRate).toHaveProperty('maxRate')
    expect(validateFilters({ ...EMPTY_FILTERS, currency: 'AE' })).toHaveProperty('currency')
    const onlyFrom = validateFilters({ ...EMPTY_FILTERS, availableFrom: '2026-12-01T09:00' })
    expect(onlyFrom).toHaveProperty('availableTo')
    const backwards = validateFilters({
      ...EMPTY_FILTERS,
      availableFrom: '2026-12-03T09:00',
      availableTo: '2026-12-01T09:00',
    })
    expect(backwards).toHaveProperty('availableTo')
    expect(validateFilters({ ...EMPTY_FILTERS, maxRate: '50', currency: 'aed' })).toEqual({})
  })

  it('adds paging and counts active filters', () => {
    const query = new URLSearchParams(apiQuery(new URLSearchParams('skill=x'), 3, 12))
    expect(query.get('page')).toBe('3')
    expect(query.get('page_size')).toBe('12')
    expect(query.get('skill')).toBe('x')
    expect(pageFromParams(new URLSearchParams('page=0'))).toBe(1)
    expect(pageFromParams(new URLSearchParams('page=4'))).toBe(4)
    expect(activeFilterCount({ ...EMPTY_FILTERS, skills: ['a', 'b'], negotiable: true })).toBe(3)
  })
})
