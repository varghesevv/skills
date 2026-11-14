import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

import { onSessionExpired } from './api/http'
import { clearTokens } from './auth/tokenStore'
import { clearFlash } from './shared/flash'

// A cold first render is slow on a busy runner; the default wait of one second made the first test
// of a file fail now and then (seen in CI). Waiting longer costs nothing when the page is ready.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  vi.unstubAllGlobals()
  clearTokens()
  onSessionExpired(null)
  clearFlash()
  document.title = ''
})
