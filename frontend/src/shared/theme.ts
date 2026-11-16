export type ThemeChoice = 'system' | 'light' | 'dark'

const KEY = 'skills.theme'

/** The saved choice. Storage can be blocked (private windows), so any failure means "system". */
export function savedTheme(): ThemeChoice {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

/** Applies and saves the choice. It lives in this browser only, not in the account. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement
  if (choice === 'system') delete root.dataset.theme
  else root.dataset.theme = choice
  try {
    if (choice === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, choice)
  } catch {
    // The choice still holds for this visit.
  }
}
