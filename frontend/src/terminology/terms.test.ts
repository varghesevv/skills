import { afterEach, describe, expect, it, vi } from 'vitest'

import profiles from './profiles.json'
import { applyTerms, setProfile, term } from './terms'

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

describe('the words of the church trust model', () => {
  it('give each profile its words for the structure and the leaders', () => {
    expect(applyTerms('{Homegroup}, {homegroups}, {verifier}, {Admin}, {owners}')).toBe(
      'Home group, home groups, verifier, Admin, owners',
    )
    setProfile('church')
    expect(applyTerms('{Verifier} and {admin} and {Owner}')).toBe(
      'Group leader and church admin and Owner',
    )
    expect(applyTerms('{a_verifier}, {a_admin}')).toBe('a group leader, a church admin')
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
    expect(applyTerms('{Organisations} and {workhosts}')).toBe('Churches and searchers')
    expect(applyTerms('I represent {a_organisation}')).toBe('I represent a church')
    expect(applyTerms('{A_workhost} helps')).toBe('A searcher helps')
    expect(applyTerms('Find {freelancers}, {a_freelancer}')).toBe('Find providers, a provider')
    expect(applyTerms('{Organisation} Name')).toBe('Church Name')
  })

  it('leaves other placeholders alone', () => {
    expect(applyTerms('{count} {freelancer}(s) on page {page}')).toBe(
      '{count} freelancer(s) on page {page}',
    )
  })
})

describe('profiles', () => {
  it('follow the chosen profile', () => {
    expect(term('organisation')).toBe('Organisation')
    setProfile('church')
    expect(term('organisation')).toBe('Church')
    expect(term('workhost')).toBe('Searcher')
    expect(term('freelancer')).toBe('Provider')
  })

  it('fall back to the default for an unknown profile', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    setProfile('nonsense')
    expect(term('organisation')).toBe('Organisation')
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})
