import { useState } from 'react'

import { t } from '../../i18n'
import { monthWeeks, periodCoversDay, type PeriodLike } from '../../shared/dates'

const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6].map((offset) =>
  // 2026-11-01 is a Sunday.
  new Date(2026, 10, 1 + offset).toLocaleDateString(undefined, { weekday: 'short' }),
)

/**
 * Month view with unavailable days marked. Shown from tablet width up; on phones the list of
 * periods below it is the whole interface (see styles/global.css).
 */
export default function MonthCalendar({ periods }: { periods: readonly PeriodLike[] }) {
  const [cursor, setCursor] = useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() }
  })

  function shift(by: number) {
    setCursor((current) => {
      const date = new Date(current.year, current.month + by, 1)
      return { year: date.getFullYear(), month: date.getMonth() }
    })
  }

  const title = new Date(cursor.year, cursor.month, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })

  return (
    <section className="calendar card" aria-label={t('availability.calendar')}>
      <div className="calendar-head">
        <button type="button" className="icon-btn" onClick={() => shift(-1)}>
          <span aria-hidden="true">‹</span>
          <span className="sr-only">{t('availability.prevMonth')}</span>
        </button>
        <h2 aria-live="polite">{title}</h2>
        <button type="button" className="icon-btn" onClick={() => shift(1)}>
          <span aria-hidden="true">›</span>
          <span className="sr-only">{t('availability.nextMonth')}</span>
        </button>
      </div>
      <table>
        <thead>
          <tr>
            {WEEKDAYS.map((name) => (
              <th key={name} scope="col">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {monthWeeks(cursor.year, cursor.month).map((week, index) => (
            <tr key={index}>
              {week.map((day, position) => {
                if (!day) return <td key={position} className="calendar-blank" />
                const off = periods.some((period) => periodCoversDay(period, day))
                return (
                  <td key={position} className={off ? 'calendar-day is-off' : 'calendar-day'}>
                    {day.getDate()}
                    {off && <span className="sr-only"> {t('availability.unavailableDay')}</span>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
