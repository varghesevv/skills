import { request } from './http'
import type { OrgBrief, WorkHostProfile, WorkHostUpdate } from './types'

export const listOrganisations = () => request<OrgBrief[]>('/organisations')

export const getHostProfile = () => request<WorkHostProfile>('/workhosts/me')

export const updateHostProfile = (body: WorkHostUpdate) =>
  request<WorkHostProfile>('/workhosts/me', { method: 'PUT', body })
