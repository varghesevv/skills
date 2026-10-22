import { describe, expect, it } from 'vitest'

import { fromLocalInput, monthWeeks, periodCoversDay, toLocalInput } from './dates'

describe('dates', () => {
  it('converts between local inputs and ISO strings without changing the moment', () => {
    const iso = fromLocalInput('2026-11-05T14:30')
    expect(iso).not.toBeNull()
    expect(toLocalInput(iso as string)).toBe('2026-11-05T14:30')
  })

  it('treats empty or broken input as missing', () => {
    expect(fromLocalInput('')).toBeNull()
    expect(fromLocalInput('not a date')).toBeNull()
  })

  it('knows which days a period touches (end is exclusive)', () => {
    const period = {
      unavailable_from: new Date(2026, 10, 5, 22, 0).toISOString(),
      unavailable_to: new Date(2026, 10, 7, 0, 0).toISOString(),
    }
    expect(periodCoversDay(period, new Date(2026, 10, 4))).toBe(false)
    expect(periodCoversDay(period, new Date(2026, 10, 5))).toBe(true)
    expect(periodCoversDay(period, new Date(2026, 10, 6))).toBe(true)
    expect(periodCoversDay(period, new Date(2026, 10, 7))).toBe(false)
  })

  it('lays a month out in whole weeks starting on Sunday', () => {
    const weeks = monthWeeks(2026, 9) // October 2026 starts on a Thursday
    expect(weeks.every((week) => week.length === 7)).toBe(true)
    expect(weeks[0]?.slice(0, 4)).toEqual([null, null, null, null])
    expect(weeks[0]?.[4]?.getDate()).toBe(1)
    expect(weeks.flat().filter(Boolean)).toHaveLength(31)
  })
})
