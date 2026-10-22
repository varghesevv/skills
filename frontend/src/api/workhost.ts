import { request } from './http'
import type {
  FreelancerPublic,
  GivenRating,
  OrgBrief,
  Page,
  SearchResult,
  WorkHostProfile,
  WorkHostUpdate,
} from './types'

export const listOrganisations = () => request<OrgBrief[]>('/organisations')

export const SEARCH_PAGE_SIZE = 12
export const GIVEN_PAGE_SIZE = 10

export const getHostProfile = () => request<WorkHostProfile>('/workhosts/me')

export const updateHostProfile = (body: WorkHostUpdate) =>
  request<WorkHostProfile>('/workhosts/me', { method: 'PUT', body })

/** `query` is a ready-made query string (see portals/workhost/searchParams.ts). */
export const searchFreelancers = (query: string) =>
  request<Page<SearchResult>>(`/search/freelancers?${query}`)

export const getFreelancer = (id: string) => request<FreelancerPublic>(`/freelancers/${id}`)

export type RatingBody = { rating: number; comment: string | null }

export const createRating = (freelancerId: string, body: RatingBody) =>
  request<GivenRating>('/ratings', {
    method: 'POST',
    body: { freelancer_id: freelancerId, ...body },
  })

export const updateRating = (ratingId: string, body: RatingBody) =>
  request<GivenRating>(`/ratings/${ratingId}`, { method: 'PUT', body })

export const listGivenRatings = (page: number) =>
  request<Page<GivenRating>>(`/workhosts/me/ratings?page=${page}&page_size=${GIVEN_PAGE_SIZE}`)
