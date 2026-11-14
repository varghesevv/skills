/** What a revocation changes, for the queries to ask again. Shared by both ways of revoking a
 *  leader so that they cannot drift apart: the lists of people, and the groups with their leaders. */
export const REVOCATION_KEYS = [
  'applicants',
  'members',
  'revoked',
  'flagged',
  'church-groups',
  'owner-churches',
] as const
