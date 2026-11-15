import { request } from './http'
import type { LabelOut, LabelType } from './types'

/** The OWNER also sees the inactive labels. */
export const listAllLabels = () => request<LabelOut[]>('/labels?include_inactive=true')

export const createLabel = (body: { label_name: string; label_type: LabelType }) =>
  request<LabelOut>('/labels', { method: 'POST', body })

export const updateLabel = (id: string, body: { label_name?: string; is_active?: boolean }) =>
  request<LabelOut>(`/labels/${id}`, { method: 'PATCH', body })
