import { request, requestFile } from './http'
import type {
  OrgProfile,
  OrgUpdate,
  Page,
  ReportData,
  ReportInfo,
  VouchedFreelancer,
} from './types'

export const VOUCHED_PAGE_SIZE = 10

export const getOrgProfile = () => request<OrgProfile>('/organisations/me')

export const updateOrgProfile = (body: OrgUpdate) =>
  request<OrgProfile>('/organisations/me', { method: 'PUT', body })

export const listVouched = (page: number) =>
  request<Page<VouchedFreelancer>>(
    `/organisations/me/freelancers?page=${page}&page_size=${VOUCHED_PAGE_SIZE}`,
  )

export const vouchFor = (freelancerId: string) =>
  request<VouchedFreelancer>(`/organisations/me/freelancers/${freelancerId}`, { method: 'POST' })

export const revokeVouch = (freelancerId: string) =>
  request<void>(`/organisations/me/freelancers/${freelancerId}`, { method: 'DELETE' })

export const listReports = () => request<ReportInfo[]>('/reports')

/** `window` is optional: without it the server uses its default (the last 30 complete days). */
function reportQuery(window: { from: string; to: string } | null, format: 'json' | 'csv') {
  const params = new URLSearchParams()
  if (window) {
    params.set('from', window.from)
    params.set('to', window.to)
  }
  params.set('format', format)
  return params.toString()
}

export const runReport = (name: string, window: { from: string; to: string } | null) =>
  request<ReportData>(`/reports/${name}?${reportQuery(window, 'json')}`)

export const downloadReportCsv = (name: string, window: { from: string; to: string } | null) =>
  requestFile(`/reports/${name}?${reportQuery(window, 'csv')}`)
