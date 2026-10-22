// The access token lives in memory only. The refresh token is kept in sessionStorage so a page
// reload can restore the session; it is cleared on logout and when the server rejects it.
// Storage can be unavailable (private windows, blocked site data), so every access is guarded.

const REFRESH_KEY = 'skills.refresh_token'

let accessToken: string | null = null
let memoryRefreshToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function getRefreshToken(): string | null {
  try {
    return sessionStorage.getItem(REFRESH_KEY) ?? memoryRefreshToken
  } catch {
    return memoryRefreshToken
  }
}

export function setTokens(access: string, refresh: string): void {
  accessToken = access
  memoryRefreshToken = refresh
  try {
    sessionStorage.setItem(REFRESH_KEY, refresh)
  } catch {
    // Storage unavailable: the in-memory copy still works until the page is closed.
  }
}

export function clearTokens(): void {
  accessToken = null
  memoryRefreshToken = null
  try {
    sessionStorage.removeItem(REFRESH_KEY)
  } catch {
    // Nothing to clear.
  }
}
