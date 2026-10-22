import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'

import { onSessionExpired } from './api/http'
import { clearTokens } from './auth/tokenStore'

afterEach(() => {
  vi.unstubAllGlobals()
  clearTokens()
  onSessionExpired(null)
  document.title = ''
})
