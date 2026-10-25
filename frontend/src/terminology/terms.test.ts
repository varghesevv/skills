import { afterEach, describe, expect, it, vi } from 'vitest'

import profiles from './profiles.json'
import { applyTerms, setProfile, slugOf, term, userTypeOfSlug } from './terms'

afterEach(() => setProfile('default'))

describe('terminology profiles', () => {
  it('give every profile the same keys', () => {
    const all = profiles as Record<string, Record<string, string>>
    const keys = Object.keys(all.default).sort()
    for (const [name, profile] of Object.entries(all)) {
      expect(Object.keys(profile).sort(), name).toEqual(keys)
      for (const value of Object.values(profile)) expect(value.trim()).not.toBe('')
    }
  })

  it('keep the default badge text equal to the plain role words', () => {
    const base = (profiles as Record<string, Record<string, string>>).default
    expect(base.badge_organisation).toBe('Organisation')
    expect(base.badge_workhost).toBe('Work host')
    expect(base.badge_freelancer).toBe('Freelancer')
  })

  it('use web-safe, distinct address words', () => {
    const all = profiles as Record<string, Record<string, string>>
    for (const [name, profile] of Object.entries(all)) {
      const paths = Object.entries(profile)
        .filter(([key]) => key.endsWith('_path'))
        .map(([, value]) => value)
      for (const path of paths) expect(path, name).toMatch(/^[a-z0-9-]+$/)
      expect(new Set(paths).size, name).toBe(paths.length)
      expect(['admin', 'login', 'register']).not.toContain(profile.organisation_path)
    }
  })
})

describe('applyTerms', () => {
  it('keeps the default words', () => {
    expect(applyTerms('Vouch for {freelancers}. {Organisations} and {workhosts}.')).toBe(
      'Vouch for freelancers. Organisations and work hosts.',
    )
    expect(applyTerms('I represent {a_organisation}')).toBe('I represent an organisation')
    expect(applyTerms('{Workhost}')).toBe('Work host')
  })

  it('switches to the church words and fixes the article', () => {
    setProfile('church')
    expect(applyTerms('{Organisations} and {workhosts}')).toBe('Churches and providers')
    expect(applyTerms('I represent {a_organisation}')).toBe('I represent a church')
    expect(applyTerms('{A_workhost} helps')).toBe('A provider helps')
    expect(applyTerms('Find {freelancers}, {a_freelancer}')).toBe('Find searchers, a searcher')
    expect(applyTerms('{Organisation} Name')).toBe('Church Name')
  })

  it('leaves other placeholders alone', () => {
    expect(applyTerms('{count} {freelancer}(s) on page {page}')).toBe(
      '{count} freelancer(s) on page {page}',
    )
  })
})

describe('addresses', () => {
  it('follow the profile', () => {
    expect(slugOf('organisation')).toBe('organisation')
    setProfile('church')
    expect(slugOf('organisation')).toBe('church')
    expect(slugOf('workhost')).toBe('provider')
    expect(slugOf('admin')).toBe('admin')
    expect(term('organisations_path')).toBe('churches')
    expect(userTypeOfSlug('church')).toBe('organisation')
    expect(userTypeOfSlug('provider')).toBe('workhost')
    expect(slugOf('freelancer')).toBe('searcher')
    expect(term('freelancers_path')).toBe('searchers')
    expect(userTypeOfSlug('searcher')).toBe('freelancer')
    expect(userTypeOfSlug('organisation')).toBeUndefined()
  })

  it('fall back to the default for an unknown profile', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    setProfile('nonsense')
    expect(slugOf('organisation')).toBe('organisation')
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })

  it('build the portal and login addresses', async () => {
    vi.resetModules()
    const terms = await import('./terms')
    terms.setProfile('church')
    const config = await import('../portals/config')
    expect(config.homePath('organisation')).toBe('/church')
    expect(config.homePath('workhost')).toBe('/provider')
    expect(config.loginPath('organisation')).toBe('/login/church')
    expect(config.loginPath('freelancer')).toBe('/login')
    expect(config.registerPath('workhost')).toBe('/register/provider')
    expect(config.loginPathFor('/church/search')).toBe('/login/church')
    const admin = config.PORTALS.find((portal) => portal.userType === 'admin')
    expect(admin?.nav.map((item) => item.to)).toContain('/admin/churches')
  })
})

describe('navigation', () => {
  it.each(Object.keys(profiles))(
    'only links to pages that exist in the %s profile',
    async (name) => {
      vi.resetModules()
      const terms = await import('./terms')
      terms.setProfile(name)
      const { PORTALS } = await import('../portals/config')
      const { freelancerRoutes } = await import('../portals/freelancer/routes')
      const { workhostRoutes } = await import('../portals/workhost/routes')
      const { organisationRoutes } = await import('../portals/organisation/routes')
      const { adminRoutes } = await import('../portals/admin/routes')
      const routes = {
        freelancer: freelancerRoutes,
        workhost: workhostRoutes,
        organisation: organisationRoutes,
        admin: adminRoutes,
      }
      for (const portal of PORTALS) {
        const known = routes[portal.userType].map((route) => (route.props as { path: string }).path)
        for (const item of portal.nav) {
          expect(item.to.startsWith(portal.path), item.to).toBe(true)
          const rest = item.to.slice(portal.path.length).replace(/^\//, '')
          if (rest) expect(known, `${name}: ${item.to}`).toContain(rest)
        }
      }
    },
  )
})
