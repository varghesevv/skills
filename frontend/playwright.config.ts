import { defineConfig } from '@playwright/test'

// The five reference viewports from docs/specification/06-frontend.md.
const VIEWPORTS = [
  { name: 'phone-small-360x640', width: 360, height: 640, mobile: true },
  { name: 'phone-390x844', width: 390, height: 844, mobile: true },
  { name: 'tablet-portrait-768x1024', width: 768, height: 1024, mobile: true },
  { name: 'tablet-landscape-1024x768', width: 1024, height: 768, mobile: true },
  { name: 'desktop-1440x900', width: 1440, height: 900, mobile: false },
]

export default defineConfig({
  testDir: './e2e',
  // The checks use a mocked API, so they need no backend. Build first (npm run e2e does).
  webServer: {
    command: 'npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: 'http://localhost:4173' },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  projects: VIEWPORTS.map((viewport) => ({
    name: viewport.name,
    use: {
      browserName: 'chromium' as const,
      viewport: { width: viewport.width, height: viewport.height },
      hasTouch: viewport.mobile,
      isMobile: viewport.mobile && viewport.width < 1024,
    },
  })),
})
