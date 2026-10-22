import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import {
  RUNS_PAGE_SIZE,
  downloadRunFile,
  listReports,
  listRuns,
  runAndKeep,
} from '../../api/reports'
import type { ReportRun } from '../../api/types'
import { t, type StringKey } from '../../i18n'
import { formatDate, formatDateTime } from '../../shared/dates'
import { saveFile } from '../../shared/download'
import { errorMessage } from '../../shared/errors'
import { checkWindow, maxDaysFor } from '../../shared/ReportCard'
import { Alert, Badge, Pager, QueryBoundary, SelectField, TextField } from '../../shared/ui'
import { usePageTitle } from '../../shared/usePageTitle'
import type { FieldErrors } from '../../shared/validation'
import { ADMIN_REPORTS_KEY, ADMIN_RUNS_KEY } from './keys'

const STATUS_TEXT: Record<ReportRun['status'], StringKey> = {
  running: 'runs.status.running',
  succeeded: 'runs.status.succeeded',
  failed: 'runs.status.failed',
}
const STATUS_TONE: Record<ReportRun['status'], 'neutral' | 'good' | 'warn'> = {
  running: 'warn',
  succeeded: 'good',
  failed: 'warn',
}

function KeepRun() {
  const queryClient = useQueryClient()
  const reports = useQuery({ queryKey: ADMIN_REPORTS_KEY, queryFn: listReports })
  const [name, setName] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<'created' | 'existing' | null>(null)

  const keep = useMutation({
    mutationFn: (input: { name: string; from: string; to: string }) =>
      runAndKeep(input.name, { from: input.from, to: input.to }),
    onSuccess: async (run) => {
      setResult(run.status === 'failed' ? null : 'created')
      if (run.status === 'failed') setError(run.error_message ?? t('error.generic'))
      await queryClient.invalidateQueries({ queryKey: ADMIN_RUNS_KEY })
    },
    onError: (failure) => setError(errorMessage(failure)),
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setResult(null)
    const found: FieldErrors = {}
    if (!name) found.report = t('runs.chooseReport')
    if (from === '' || to === '') found.to = t('reports.needBoth')
    else Object.assign(found, checkWindow(from, to, maxDaysFor(name)).errors)
    setErrors(found)
    if (Object.keys(found).length === 0) keep.mutate({ name, from, to })
  }

  return (
    <form onSubmit={onSubmit} noValidate className="card form-grid cols-2">
      <h2 className="span-2">{t('runs.keepTitle')}</h2>
      <p className="muted span-2">{t('runs.keepLead')}</p>
      {error && (
        <div className="span-2">
          <Alert kind="error" focus>
            {error}
          </Alert>
        </div>
      )}
      {result && (
        <div className="span-2">
          <Alert kind="success">{t('runs.kept')}</Alert>
        </div>
      )}
      <div className="span-2">
        <SelectField
          label={t('runs.report')}
          name="keep_report"
          value={name}
          onChange={setName}
          options={[
            { value: '', label: t('runs.chooseReport') },
            ...(reports.data ?? []).map((report) => ({ value: report.name, label: report.title })),
          ]}
          error={errors.report}
        />
      </div>
      <TextField
        label={t('reports.from')}
        name="keep_from"
        type="date"
        value={from}
        onChange={setFrom}
        error={errors.from}
      />
      <TextField
        label={t('reports.to')}
        name="keep_to"
        type="date"
        value={to}
        onChange={setTo}
        error={errors.to}
      />
      <button type="submit" className="btn btn-primary span-2" disabled={keep.isPending}>
        {keep.isPending ? t('reports.running') : t('runs.keepAction')}
      </button>
    </form>
  )
}

function RunRow({ run, title }: { run: ReportRun; title: string }) {
  const [error, setError] = useState<string | null>(null)
  const download = useMutation({
    mutationFn: (format: 'csv' | 'html') => downloadRunFile(run.id, format),
    onSuccess: saveFile,
    onError: (failure) => setError(errorMessage(failure)),
  })
  return (
    <tr>
      <td>{title}</td>
      <td>
        {formatDate(run.window_from)} → {formatDate(run.window_to)}
      </td>
      <td>
        <Badge tone={STATUS_TONE[run.status]}>{t(STATUS_TEXT[run.status])}</Badge>
        {run.error_message && <div className="muted">{run.error_message}</div>}
      </td>
      <td>{run.row_count ?? ''}</td>
      <td>{formatDateTime(run.started_at)}</td>
      <td>
        {run.has_files ? (
          <div className="row-actions">
            <button
              type="button"
              className="btn btn-quiet"
              disabled={download.isPending}
              onClick={() => {
                setError(null)
                download.mutate('csv')
              }}
              aria-label={`${t('runs.csv')}: ${title}`}
            >
              {t('runs.csv')}
            </button>
            <button
              type="button"
              className="btn btn-quiet"
              disabled={download.isPending}
              onClick={() => {
                setError(null)
                download.mutate('html')
              }}
              aria-label={`${t('runs.html')}: ${title}`}
            >
              {t('runs.html')}
            </button>
          </div>
        ) : (
          <span className="muted">{t('runs.noFiles')}</span>
        )}
        {error && <div className="muted">{error}</div>}
      </td>
    </tr>
  )
}

export default function RunsPage() {
  usePageTitle(t('runs.title'))
  const [page, setPage] = useState(1)
  const [reportName, setReportName] = useState('')
  const [status, setStatus] = useState('')
  const reports = useQuery({ queryKey: ADMIN_REPORTS_KEY, queryFn: listReports })
  const titles = new Map((reports.data ?? []).map((report) => [report.name, report.title]))
  const query = useQuery({
    queryKey: [...ADMIN_RUNS_KEY, page, reportName, status],
    queryFn: () => listRuns(page, reportName, status),
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <h1>{t('runs.title')}</h1>
      <p className="lead">{t('runs.lead')}</p>
      <div className="stack">
        <KeepRun />
        <div className="toolbar">
          <SelectField
            label={t('runs.report')}
            name="filter_report"
            value={reportName}
            onChange={(value) => {
              setReportName(value)
              setPage(1)
            }}
            options={[
              { value: '', label: t('runs.allReports') },
              ...(reports.data ?? []).map((report) => ({
                value: report.name,
                label: report.title,
              })),
            ]}
          />
          <SelectField
            label={t('runs.statusLabel')}
            name="filter_status"
            value={status}
            onChange={(value) => {
              setStatus(value)
              setPage(1)
            }}
            options={[
              { value: '', label: t('runs.anyStatus') },
              { value: 'succeeded', label: t('runs.status.succeeded') },
              { value: 'failed', label: t('runs.status.failed') },
              { value: 'running', label: t('runs.status.running') },
            ]}
          />
        </div>
        <QueryBoundary query={query}>
          {(data) =>
            data.total === 0 ? (
              <p className="muted">{t('runs.empty')}</p>
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <caption>{t('runs.history')}</caption>
                    <thead>
                      <tr>
                        <th scope="col">{t('runs.report')}</th>
                        <th scope="col">{t('runs.window')}</th>
                        <th scope="col">{t('runs.statusLabel')}</th>
                        <th scope="col">{t('runs.rows')}</th>
                        <th scope="col">{t('runs.started')}</th>
                        <th scope="col">{t('runs.files')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((run) => (
                        <RunRow
                          key={run.id}
                          run={run}
                          title={titles.get(run.report_name) ?? run.report_name}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pager
                  page={data.page}
                  pageSize={RUNS_PAGE_SIZE}
                  total={data.total}
                  onChange={setPage}
                />
              </>
            )
          }
        </QueryBoundary>
      </div>
    </>
  )
}
