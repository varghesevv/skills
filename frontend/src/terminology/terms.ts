// The words used for the three kinds of people, chosen per installation (see profiles.json).
// Screen text uses tokens such as {organisation}; web addresses use the *_path values.

import profiles from './profiles.json'

type Profile = Record<string, string>

const PROFILES = profiles as Record<string, Profile>
export const DEFAULT_PROFILE = 'default'

let activeName = DEFAULT_PROFILE
let active: Profile = PROFILES[DEFAULT_PROFILE]

export function profileNames(): string[] {
  return Object.keys(PROFILES)
}

export function activeProfile(): string {
  return activeName
}

/** Use the named profile; an unknown name falls back to the default one. */
export function setProfile(name: string | undefined): void {
  const wanted = (name ?? '').trim()
  if (wanted && PROFILES[wanted]) {
    activeName = wanted
    active = PROFILES[wanted]
    return
  }
  if (wanted) console.warn(`Unknown terminology profile "${wanted}"; using "${DEFAULT_PROFILE}".`)
  activeName = DEFAULT_PROFILE
  active = PROFILES[DEFAULT_PROFILE]
}

/** One value of the active profile, for example term('organisation_path'). */
export function term(key: string): string {
  const value = active[key] ?? PROFILES[DEFAULT_PROFILE][key]
  if (value === undefined) throw new Error(`Unknown term: ${key}`)
  return value
}

const KINDS = ['organisation', 'workhost', 'freelancer'] as const

function article(word: string): string {
  return /^[aeiou]/i.test(word) ? 'an' : 'a'
}

function lowerFirst(word: string): string {
  return word.charAt(0).toLowerCase() + word.slice(1)
}

function upperFirst(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1)
}

/**
 * Replaces the term tokens in a text:
 *   {organisation}  -> "church" (lower case)     {Organisation}  -> "Church" (as written)
 *   {organisations} -> "churches"                 {Organisations} -> "Churches"
 *   {a_organisation} -> "a church" / "an organisation"   {A_organisation} -> "A church"
 * The same works for workhost and freelancer. Other {names} are left for t() parameters.
 */
export function applyTerms(text: string): string {
  return text.replace(/\{(A_|a_)?([A-Za-z]+)\}/g, (match, prefix: string | undefined, name) => {
    const lower = lowerFirst(name)
    const base = lower.endsWith('s') ? lower.slice(0, -1) : lower
    if (!(KINDS as readonly string[]).includes(base)) return match
    const written = term(lower)
    const capital = name.charAt(0) === name.charAt(0).toUpperCase()
    if (prefix) {
      const word = lowerFirst(written)
      const phrase = `${article(word)} ${word}`
      return prefix === 'A_' ? upperFirst(phrase) : phrase
    }
    return capital ? written : lowerFirst(written)
  })
}

export type PathUserType = 'freelancer' | 'workhost' | 'organisation'

/** The address segment for a kind of account, for example "church" for organisations. */
export function slugOf(userType: PathUserType | 'admin'): string {
  return userType === 'admin' ? 'admin' : term(`${userType}_path`)
}

/** The account kind behind an address segment, or undefined if it is not one of them. */
export function userTypeOfSlug(slug: string | undefined): PathUserType | undefined {
  return (['freelancer', 'workhost', 'organisation'] as const).find((kind) => slugOf(kind) === slug)
}

/**
 * Reads the profile name before the app starts. The web server answers /config.json from its
 * TERMINOLOGY_PROFILE setting; in development the VITE_TERMINOLOGY_PROFILE setting is used.
 */
export async function loadTerminology(): Promise<void> {
  let name: string | undefined = import.meta.env.VITE_TERMINOLOGY_PROFILE as string | undefined
  try {
    const response = await fetch('/config.json', { cache: 'no-store' })
    if (response.ok && (response.headers.get('content-type') ?? '').includes('json')) {
      const data = (await response.json()) as { terminology?: string }
      if (data.terminology) name = data.terminology
    }
  } catch {
    // No config: keep the default.
  }
  setProfile(name)
}
