import { request } from './http'
import type {
  FreelancerPublic,
  GivenRating,
  Page,
  RevealedMobile,
  RevealRequest,
  SearchResult,
} from './types'

export const SEARCH_PAGE_SIZE = 12
export const GIVEN_PAGE_SIZE = 10

/** `query` is a ready-made query string (see pages/person/search/searchParams.ts). */
export const searchProviders = (query: string) =>
  request<Page<SearchResult>>(`/search/freelancers?${query}`)

export const getProvider = (id: string) => request<FreelancerPublic>(`/freelancers/${id}`)

/** The only call that returns a mobile number. Every call is recorded and rate limited. */
export const revealMobile = (providerId: string, body: RevealRequest) =>
  request<RevealedMobile>(`/freelancers/${providerId}/reveal-mobile`, { method: 'POST', body })

export type RatingBody = { rating: number; comment: string | null }

export const createRating = (providerId: string, body: RatingBody) =>
  request<GivenRating>('/ratings', {
    method: 'POST',
    body: { provider_id: providerId, ...body },
  })

export const updateRating = (ratingId: string, body: RatingBody) =>
  request<GivenRating>(`/ratings/${ratingId}`, { method: 'PUT', body })

/** The ratings the caller gave. The path keeps its older name (decision D-43). */
export const listGivenRatings = (page: number) =>
  request<Page<GivenRating>>(`/workhosts/me/ratings?page=${page}&page_size=${GIVEN_PAGE_SIZE}`)
