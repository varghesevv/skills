import { request } from './http'
import type { ApprovalStatus, LabelOut, LabelType, OrgSummary, Page } from './types'

export const ORGS_PAGE_SIZE = 10

export const listOrganisationsByStatus = (status: ApprovalStatus, page: number) =>
  request<Page<OrgSummary>>(
    `/admin/organisations?status=${status}&page=${page}&page_size=${ORGS_PAGE_SIZE}`,
  )

export const decideOrganisation = (id: string, decision: 'approve' | 'reject') =>
  request<OrgSummary>(`/admin/organisations/${id}/${decision}`, { method: 'POST' })

/** Admins also see inactive labels. */
export const listAllLabels = () => request<LabelOut[]>('/labels?include_inactive=true')

export const createLabel = (body: { label_name: string; label_type: LabelType }) =>
  request<LabelOut>('/labels', { method: 'POST', body })

export const updateLabel = (id: string, body: { label_name?: string; is_active?: boolean }) =>
  request<LabelOut>(`/labels/${id}`, { method: 'PATCH', body })
