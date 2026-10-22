import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { downloadReportCsv, listReports, runReport } from '../../api/organisation'
import type { ReportData, ReportInfo } from '../../api/types'
import { t } from '../../i18n'
import { errorMessage } from '../../shared/errors'
import { Alert, QueryBoundary, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import type { FieldErrors } from '../../shared/validation'
import { REPORTS_KEY } from './keys'

// Ids are for the server; people read names.
const HIDDEN_COLUMNS = new Set(['org_id'])

function ReportTable({ data }: { data: ReportData }) {
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

const MAX_WINDOW_DAYS = 366 // the same limit the server applies
const DAY_MS = 24 * 60 * 60 * 1000

type Window = { from: string; to: string }

/** Both dates or neither (neither means the server's default: the last 30 days). */
export function checkWindow(
  from: string,
  to: string,
): { window: Window | null; errors: FieldErrors } {
  if (from === '' && to === '') return { window: null, errors: {} }
  if (from === '') return { window: null, errors: { from: t('reports.needBoth') } }
  if (to === '') return { window: null, errors: { to: t('reports.needBoth') } }
  const days = (Date.parse(to) - Date.parse(from)) / DAY_MS
  if (days < 0) return { window: null, errors: { to: t('reports.order') } }
  if (days + 1 > MAX_WINDOW_DAYS) {
    return { window: null, errors: { to: t('reports.tooLong', { days: MAX_WINDOW_DAYS }) } }
  }
  return { window: { from, to }, errors: {} }
}

function ReportCard({ report }: { report: ReportInfo }) {
  const [data, setData] = useState<ReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})

  /** The checked window, or `undefined` when the dates are not valid (errors are then shown). */
  function chosenWindow(): Window | null | undefined {
    const checked = checkWindow(from, to)
    setErrors(checked.errors)
    setError(null)
    return Object.keys(checked.errors).length > 0 ? undefined : checked.window
  }

  const run = useMutation({
    mutationFn: (window: Window | null) => runReport(report.name, window),
    onSuccess: setData,
    onError: (failure) => setError(errorMessage(failure)),
  })
  const download = useMutation({
    mutationFn: (window: Window | null) => downloadReportCsv(report.name, window),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

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
      </div>
      <div className="row-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={run.isPending}
          onClick={() => {
            const window = chosenWindow()
            if (window !== undefined) run.mutate(window)
          }}
        >
          {run.isPending ? t('reports.running') : t('reports.run')}
        </button>
        <button
          type="button"
          className="btn btn-quiet"
          disabled={download.isPending}
          onClick={() => {
            const window = chosenWindow()
            if (window !== undefined) download.mutate(window)
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

export default function ReportsPage() {
  usePageTitle(t('reports.title'))
  const query = useQuery({ queryKey: REPORTS_KEY, queryFn: listReports })
  return (
    <>
      <h1>{t('reports.title')}</h1>
      <p className="lead">{t('reports.lead')}</p>
      <QueryBoundary query={query}>
        {(reports) => (
          <div className="stack">
            {reports.map((report) => (
              <ReportCard key={report.name} report={report} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </>
  )
}
