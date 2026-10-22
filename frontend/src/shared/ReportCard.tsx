import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { downloadReportCsv, runReport, type ReportFilters, type ReportWindow } from '../api/reports'
import type { OrgBrief, ReportData, ReportInfo } from '../api/types'
import { t } from '../i18n'
import { saveFile } from './download'
import { errorMessage } from './errors'
import { Alert, SelectField, TextField } from './ui'
import type { FieldErrors } from './validation'

// Ids are for the server; people read names.
const HIDDEN_COLUMNS = new Set(['org_id'])

export function ReportTable({ data }: { data: ReportData }) {
  return (
    <>
      {data.sections.map((section) => {
        const shown = section.columns
          .map((name, index) => ({ name, index }))
          .filter((column) => !HIDDEN_COLUMNS.has(column.name))
        return (
          <div key={section.title} className="table-wrap">
            <table>
              <caption>{section.title}</caption>
              <thead>
                <tr>
                  {shown.map((column) => (
                    <th key={column.name} scope="col">
                      {column.name.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {section.rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {shown.map((column) => (
                      <td key={column.name}>{String(row[column.index] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}
    </>
  )
}

const DAY_MS = 24 * 60 * 60 * 1000
export const MAX_WINDOW_DAYS = 366 // the same limit the server applies
const SHORT_WINDOWS: Record<string, number> = { availability_overview: 93 }

export function maxDaysFor(reportName: string): number {
  return SHORT_WINDOWS[reportName] ?? MAX_WINDOW_DAYS
}

/** Both dates or neither (neither means the server's default: the last 30 days). */
export function checkWindow(
  from: string,
  to: string,
  maxDays = MAX_WINDOW_DAYS,
): { window: ReportWindow | null; errors: FieldErrors } {
  if (from === '' && to === '') return { window: null, errors: {} }
  if (from === '') return { window: null, errors: { from: t('reports.needBoth') } }
  if (to === '') return { window: null, errors: { to: t('reports.needBoth') } }
  const days = (Date.parse(to) - Date.parse(from)) / DAY_MS
  if (days < 0) return { window: null, errors: { to: t('reports.order') } }
  if (days + 1 > maxDays)
    return { window: null, errors: { to: t('reports.tooLong', { days: maxDays }) } }
  return { window: { from, to }, errors: {} }
}

const USER_TYPES = ['freelancer', 'workhost', 'organisation', 'admin'] as const

type FilterState = {
  user_type: string
  skill: string
  currency: string
  min_ratings: string
  org_id: string
}
const NO_FILTERS: FilterState = {
  user_type: '',
  skill: '',
  currency: '',
  min_ratings: '',
  org_id: '',
}

function checkFilters(
  report: ReportInfo,
  values: FilterState,
): { filters: ReportFilters; errors: FieldErrors } {
  const errors: FieldErrors = {}
  const filters: ReportFilters = {}
  if (report.filters.includes('user_type') && values.user_type) filters.user_type = values.user_type
  if (report.filters.includes('org_id') && values.org_id) filters.org_id = values.org_id
  if (report.filters.includes('skill') && values.skill.trim()) filters.skill = values.skill.trim()
  if (report.filters.includes('currency') && values.currency.trim()) {
    if (/^[A-Za-z]{3}$/.test(values.currency.trim()))
      filters.currency = values.currency.trim().toUpperCase()
    else errors.currency = t('validation.currency')
  }
  if (report.filters.includes('min_ratings') && values.min_ratings.trim()) {
    const count = Number(values.min_ratings.trim())
    if (Number.isInteger(count) && count >= 1 && count <= 1000) filters.min_ratings = String(count)
    else errors.min_ratings = t('reports.minRatingsInvalid')
  }
  return { filters, errors }
}

/**
 * Run one report for a date range and show it as a table, with a CSV download.
 * `withFilters` adds the report's own filters (admins); organisations only get the dates.
 */
export function ReportCard({
  report,
  withFilters = false,
  organisations = [],
}: {
  report: ReportInfo
  withFilters?: boolean
  organisations?: OrgBrief[]
}) {
  const [data, setData] = useState<ReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [values, setValues] = useState(NO_FILTERS)
  const [errors, setErrors] = useState<FieldErrors>({})
  const set = (name: keyof FilterState) => (value: string) =>
    setValues((current) => ({ ...current, [name]: value }))

  type Chosen = { window: ReportWindow | null; filters: ReportFilters }
  /** The checked inputs, or `undefined` when something is invalid (the errors are then shown). */
  function chosen(): Chosen | undefined {
    const checkedWindow = checkWindow(from, to, maxDaysFor(report.name))
    const checkedFilters = withFilters ? checkFilters(report, values) : { filters: {}, errors: {} }
    const all = { ...checkedWindow.errors, ...checkedFilters.errors }
    setErrors(all)
    setError(null)
    if (Object.keys(all).length > 0) return undefined
    return { window: checkedWindow.window, filters: checkedFilters.filters }
  }

  const run = useMutation({
    mutationFn: (input: Chosen) => runReport(report.name, input.window, input.filters),
    onSuccess: setData,
    onError: (failure) => setError(errorMessage(failure)),
  })
  const download = useMutation({
    mutationFn: (input: Chosen) => downloadReportCsv(report.name, input.window, input.filters),
    onSuccess: saveFile,
    onError: (failure) => setError(errorMessage(failure)),
  })

  const has = (filter: string) => withFilters && report.filters.includes(filter)

  return (
    <section className="card" aria-labelledby={`report-${report.name}`}>
      <h2 id={`report-${report.name}`}>{report.title}</h2>
      <p className="muted">{report.description}</p>
      {error && (
        <Alert kind="error" focus>
          {error}
        </Alert>
      )}
      <div className="form-grid cols-2">
        <TextField
          label={t('reports.from')}
          name={`from-${report.name}`}
          type="date"
          value={from}
          onChange={setFrom}
          error={errors.from}
        />
        <TextField
          label={t('reports.to')}
          name={`to-${report.name}`}
          type="date"
          hint={t('reports.windowHint')}
          value={to}
          onChange={setTo}
          error={errors.to}
        />
        {has('user_type') && (
          <SelectField
            label={t('reports.userType')}
            name={`user_type-${report.name}`}
            value={values.user_type}
            onChange={set('user_type')}
            options={[
              { value: '', label: t('reports.anyUserType') },
              ...USER_TYPES.map((type) => ({ value: type, label: t(`role.${type}`) })),
            ]}
          />
        )}
        {has('org_id') && organisations.length > 0 && (
          <SelectField
            label={t('reports.organisation')}
            name={`org_id-${report.name}`}
            value={values.org_id}
            onChange={set('org_id')}
            options={[
              { value: '', label: t('search.anyOrg') },
              ...organisations.map((item) => ({ value: item.id, label: item.org_name })),
            ]}
          />
        )}
        {has('skill') && (
          <TextField
            label={t('reports.skill')}
            name={`skill-${report.name}`}
            value={values.skill}
            onChange={set('skill')}
          />
        )}
        {has('currency') && (
          <TextField
            label={t('profile.currency')}
            name={`currency-${report.name}`}
            maxLength={3}
            hint={t('profile.currencyHint')}
            value={values.currency}
            onChange={set('currency')}
            error={errors.currency}
          />
        )}
        {has('min_ratings') && (
          <TextField
            label={t('reports.minRatings')}
            name={`min_ratings-${report.name}`}
            inputMode="numeric"
            value={values.min_ratings}
            onChange={set('min_ratings')}
            error={errors.min_ratings}
          />
        )}
      </div>
      <div className="row-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={run.isPending}
          onClick={() => {
            const input = chosen()
            if (input) run.mutate(input)
          }}
        >
          {run.isPending ? t('reports.running') : t('reports.run')}
        </button>
        <button
          type="button"
          className="btn btn-quiet"
          disabled={download.isPending}
          onClick={() => {
            const input = chosen()
            if (input) download.mutate(input)
          }}
        >
          {t('reports.csv')}
        </button>
      </div>
      {data &&
        (data.row_count === 0 ? (
          <p className="muted">{t('reports.noRows')}</p>
        ) : (
          <ReportTable data={data} />
        ))}
    </section>
  )
}
