import type { RegisterType, UserType } from '../api/types'
import type { StringKey } from '../i18n'
import { slugOf, term } from '../terminology/terms'

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
    path: `/${slugOf('freelancer')}`,
    roleKey: 'role.freelancer',
    leadKey: 'dashboard.lead.freelancer',
    nav: [
      { to: `/${slugOf('freelancer')}`, labelKey: 'nav.dashboard', end: true },
      { to: `/${slugOf('freelancer')}/profile`, labelKey: 'nav.profile' },
      { to: `/${slugOf('freelancer')}/labels`, labelKey: 'nav.labels' },
      { to: `/${slugOf('freelancer')}/availability`, labelKey: 'nav.availability' },
      { to: `/${slugOf('freelancer')}/ratings`, labelKey: 'nav.ratings' },
      { to: `/${slugOf('freelancer')}/vouches`, labelKey: 'nav.vouches' },
    ],
  },
  {
    userType: 'workhost',
    path: `/${slugOf('workhost')}`,
    roleKey: 'role.workhost',
    leadKey: 'dashboard.lead.workhost',
    nav: [
      { to: `/${slugOf('workhost')}`, labelKey: 'nav.dashboard', end: true },
      { to: `/${slugOf('workhost')}/search`, labelKey: 'nav.search' },
      { to: `/${slugOf('workhost')}/ratings`, labelKey: 'nav.given' },
      { to: `/${slugOf('workhost')}/profile`, labelKey: 'nav.profile' },
    ],
  },
  {
    userType: 'organisation',
    path: `/${slugOf('organisation')}`,
    roleKey: 'role.organisation',
    leadKey: 'dashboard.lead.organisation',
    nav: [
      { to: `/${slugOf('organisation')}`, labelKey: 'nav.dashboard', end: true },
      { to: `/${slugOf('organisation')}/freelancers`, labelKey: 'nav.vouched' },
      { to: `/${slugOf('organisation')}/search`, labelKey: 'nav.search' },
      { to: `/${slugOf('organisation')}/reports`, labelKey: 'nav.reports' },
      { to: `/${slugOf('organisation')}/profile`, labelKey: 'nav.profile' },
    ],
  },
  {
    userType: 'admin',
    path: '/admin',
    roleKey: 'role.admin',
    leadKey: 'dashboard.lead.admin',
    nav: [
      { to: '/admin', labelKey: 'nav.dashboard', end: true },
      { to: `/admin/${term('organisations_path')}`, labelKey: 'nav.orgs' },
      { to: '/admin/reports', labelKey: 'nav.reports' },
      { to: '/admin/report-history', labelKey: 'nav.runs' },
      { to: '/admin/report-schedules', labelKey: 'nav.schedules' },
      { to: '/admin/labels', labelKey: 'nav.adminLabels' },
    ],
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

/** An address inside a portal, for example portalPath('organisation', 'search'). */
export function portalPath(userType: UserType, ...parts: string[]): string {
  return ['', slugOf(userType), ...parts].join('/')
}

/** The address of the page where a kind of account registers. */
export function registerPath(userType: RegisterType): string {
  return `/register/${slugOf(userType)}`
}

/** The login page of each kind of account. Freelancers have the main /login page. */
export function loginPath(userType: UserType): string {
  return userType === 'freelancer' ? '/login' : `/login/${slugOf(userType)}`
}

/** The login page that fits a protected address, so an admin link leads to the admin login. */
export function loginPathFor(pathname: string): string {
  const portal = PORTALS.find(
    (item) => pathname === item.path || pathname.startsWith(`${item.path}/`),
  )
  return portal ? loginPath(portal.userType) : '/login'
}
