// Dates travel to and from the API as ISO 8601 with a time zone. The browser's date and time
// inputs work in local time, so these helpers convert between the two.

const pad = (value: number) => String(value).padStart(2, '0')

/** ISO string -> value for <input type="datetime-local"> in local time. */
export function toLocalInput(iso: string): string {
  const date = new Date(iso)
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** Value of a datetime-local input (local time) -> ISO string in UTC, or null if empty/invalid. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export type PeriodLike = { unavailable_from: string; unavailable_to: string }

/** True when the period touches any moment of the given local calendar day. */
export function periodCoversDay(period: PeriodLike, day: Date): boolean {
  const start = new Date(day.getFullYear(), day.getMonth(), day.getDate())
  const end = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1)
  return new Date(period.unavailable_from) < end && new Date(period.unavailable_to) > start
}

/** Weeks (Sunday first) for a month; days outside the month are null. */
export function monthWeeks(year: number, month: number): (Date | null)[][] {
  const first = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: (Date | null)[] = Array.from({ length: first.getDay() }, () => null)
  for (let day = 1; day <= daysInMonth; day += 1) cells.push(new Date(year, month, day))
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks: (Date | null)[][] = []
  for (let index = 0; index < cells.length; index += 7) weeks.push(cells.slice(index, index + 7))
  return weeks
}
