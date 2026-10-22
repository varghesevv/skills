import { request, requestFile } from './http'
import type { Page, ReportData, ReportInfo, ReportRun, ReportSchedule } from './types'

export const RUNS_PAGE_SIZE = 10

export type ReportWindow = { from: string; to: string }
/** Extra report filters by API name (user_type, skill, currency, min_ratings, org_id). */
export type ReportFilters = Record<string, string>

export const listReports = () => request<ReportInfo[]>('/reports')

/** `window` null means the server's default (the last 30 complete days). */
function query(window: ReportWindow | null, format: 'json' | 'csv', filters: ReportFilters) {
  const params = new URLSearchParams()
  if (window) {
    params.set('from', window.from)
    params.set('to', window.to)
  }
  for (const [name, value] of Object.entries(filters)) if (value) params.set(name, value)
  params.set('format', format)
  return params.toString()
}

export const runReport = (name: string, window: ReportWindow | null, filters: ReportFilters = {}) =>
  request<ReportData>(`/reports/${name}?${query(window, 'json', filters)}`)

export const downloadReportCsv = (
  name: string,
  window: ReportWindow | null,
  filters: ReportFilters = {},
) => requestFile(`/reports/${name}?${query(window, 'csv', filters)}`)

// ---- admin: kept runs and schedules ----

export const listRuns = (page: number, reportName: string, status: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(RUNS_PAGE_SIZE) })
  if (reportName) params.set('report_name', reportName)
  if (status) params.set('status', status)
  return request<Page<ReportRun>>(`/reports/runs?${params.toString()}`)
}

export const runAndKeep = (name: string, window: ReportWindow) =>
  request<ReportRun>(`/reports/${name}/run`, {
    method: 'POST',
    body: { date_from: window.from, date_to: window.to },
  })

export const downloadRunFile = (id: string, format: 'csv' | 'html') =>
  requestFile(`/reports/runs/${id}/download?format=${format}`)

export const listSchedules = () => request<ReportSchedule[]>('/reports/schedules')

export const updateSchedule = (name: string, body: Omit<ReportSchedule, 'report_name'>) =>
  request<ReportSchedule>(`/reports/schedules/${name}`, { method: 'PUT', body })
