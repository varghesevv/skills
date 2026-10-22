import { request } from './http'
import type {
  FreelancerLabel,
  FreelancerProfile,
  LabelOut,
  LabelSelection,
  Page,
  ProfileUpdate,
  PublicRating,
  Unavailability,
  Vouch,
} from './types'

export const RATINGS_PAGE_SIZE = 10

export const getProfile = () => request<FreelancerProfile>('/freelancers/me')

export const updateProfile = (body: ProfileUpdate) =>
  request<FreelancerProfile>('/freelancers/me', { method: 'PUT', body })

export const listLabels = () => request<LabelOut[]>('/labels')

export const replaceLabels = (labels: LabelSelection[]) =>
  request<FreelancerLabel[]>('/freelancers/me/labels', { method: 'PUT', body: { labels } })

export type Period = { unavailable_from: string; unavailable_to: string }

export const listUnavailability = () => request<Unavailability[]>('/freelancers/me/unavailability')

export const addUnavailability = (body: Period) =>
  request<Unavailability>('/freelancers/me/unavailability', { method: 'POST', body })

export const updateUnavailability = (id: string, body: Period) =>
  request<Unavailability>(`/freelancers/me/unavailability/${id}`, { method: 'PUT', body })

export const deleteUnavailability = (id: string) =>
  request<void>(`/freelancers/me/unavailability/${id}`, { method: 'DELETE' })

export const listVouches = () => request<Vouch[]>('/freelancers/me/vouches')

export const decideVouch = (orgId: string, decision: 'accept' | 'reject') =>
  request<Vouch>(`/freelancers/me/vouches/${orgId}/${decision}`, { method: 'POST' })

export const listRatings = (freelancerId: string, page: number) =>
  request<Page<PublicRating>>(
    `/freelancers/${freelancerId}/ratings?page=${page}&page_size=${RATINGS_PAGE_SIZE}`,
  )
