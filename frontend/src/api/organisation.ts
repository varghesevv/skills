import { request } from './http'
import type { OrgProfile, OrgUpdate, Page, VouchedFreelancer } from './types'

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
