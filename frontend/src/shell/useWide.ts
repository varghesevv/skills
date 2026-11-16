import { useEffect, useState } from 'react'

/** Does the screen match this media query? Where the browser cannot tell (tests), `unknown`. */
export function useMedia(query: string, unknown: boolean): boolean {
  const read = () =>
    typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : unknown
  const [matches, setMatches] = useState(read)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const list = window.matchMedia(query)
    if (typeof list.addEventListener !== 'function') return
    const onChange = () => setMatches(list.matches)
    onChange()
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [query])
  return matches
}

// The two breakpoints of global.css.

/** From the tablet width up (640px). Unknown counts as wide. */
export const useWide = () => useMedia('(min-width: 640px)', true)

/** From the desktop width up (1024px). Unknown counts as narrow. */
export const useDesktop = () => useMedia('(min-width: 1024px)', false)
