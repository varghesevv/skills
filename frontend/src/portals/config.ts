import type { UserType } from '../api/types'
import type { StringKey } from '../i18n'

export type NavItem = { to: string; labelKey: StringKey; end?: boolean }

export type Portal = {
  userType: UserType
  path: string
  roleKey: StringKey
  leadKey: StringKey
  nav: readonly NavItem[]
}

// Later steps add each portal's pages to `nav` and to the routes in App.tsx.
export const PORTALS: readonly Portal[] = [
  {
    userType: 'freelancer',
    path: '/freelancer',
    roleKey: 'role.freelancer',
    leadKey: 'dashboard.lead.freelancer',
    nav: [
      { to: '/freelancer', labelKey: 'nav.dashboard', end: true },
      { to: '/freelancer/profile', labelKey: 'nav.profile' },
      { to: '/freelancer/labels', labelKey: 'nav.labels' },
      { to: '/freelancer/availability', labelKey: 'nav.availability' },
      { to: '/freelancer/ratings', labelKey: 'nav.ratings' },
      { to: '/freelancer/vouches', labelKey: 'nav.vouches' },
    ],
  },
  {
    userType: 'workhost',
    path: '/workhost',
    roleKey: 'role.workhost',
    leadKey: 'dashboard.lead.workhost',
    nav: [
      { to: '/workhost', labelKey: 'nav.dashboard', end: true },
      { to: '/workhost/search', labelKey: 'nav.search' },
      { to: '/workhost/ratings', labelKey: 'nav.given' },
      { to: '/workhost/profile', labelKey: 'nav.profile' },
    ],
  },
  {
    userType: 'organisation',
    path: '/organisation',
    roleKey: 'role.organisation',
    leadKey: 'dashboard.lead.organisation',
    nav: [
      { to: '/organisation', labelKey: 'nav.dashboard', end: true },
      { to: '/organisation/freelancers', labelKey: 'nav.vouched' },
      { to: '/organisation/search', labelKey: 'nav.search' },
      { to: '/organisation/reports', labelKey: 'nav.reports' },
      { to: '/organisation/profile', labelKey: 'nav.profile' },
    ],
  },
  {
    userType: 'admin',
    path: '/admin',
    roleKey: 'role.admin',
    leadKey: 'dashboard.lead.admin',
    nav: [{ to: '/admin', labelKey: 'nav.dashboard', end: true }],
  },
]

export function portalFor(userType: UserType): Portal {
  const portal = PORTALS.find((item) => item.userType === userType)
  if (!portal) throw new Error(`Unknown user type: ${userType}`)
  return portal
}

export function homePath(userType: UserType): string {
  return portalFor(userType).path
}

/** Where to go after login: the page the person wanted if it is in their portal, else home. */
export function landingTarget(userType: UserType, from: unknown): string {
  const home = homePath(userType)
  if (typeof from === 'string' && (from === home || from.startsWith(`${home}/`))) return from
  return home
}
