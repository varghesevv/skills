import { expect, test, type Page, type TestInfo } from '@playwright/test'

import { mockApi, type Role } from './mockApi'

// Acceptance criteria 1, 3 and 4 in docs/specification/06-frontend.md: no sideways page scroll,
// large enough touch targets, and the navigation changing with the screen size. Every
// scenario runs at all five reference viewports (one Playwright project each) and keeps a
// full-page screenshot for review.

type Scenario = {
  name: string
  role: Role | null
  path: string
  /** Wait for the page to finish loading, and do anything needed to show its widest content. */
  ready: (page: Page) => Promise<void>
}

const SCENARIOS: Scenario[] = [
  {
    name: 'login',
    role: null,
    path: '/login',
    ready: async (page) => {
      await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
    },
  },
  {
    name: 'register',
    role: null,
    path: '/register/freelancer',
    ready: async (page) => {
      await expect(page.getByLabel('Full name')).toBeVisible()
    },
  },
  {
    name: 'dashboard',
    role: 'freelancer',
    path: '/freelancer',
    ready: async (page) => {
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    },
  },
  {
    name: 'form page (profile)',
    role: 'freelancer',
    path: '/freelancer/profile',
    ready: async (page) => {
      await expect(page.getByLabel('Rate per hour')).toBeVisible()
    },
  },
  {
    name: 'search',
    role: 'workhost',
    path: '/workhost/search',
    ready: async (page) => {
      await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
    },
  },
  {
    name: 'search with the filter panel open',
    role: 'workhost',
    path: '/workhost/search',
    ready: async (page) => {
      await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
      const toggle = page.getByRole('button', { name: 'Filters', exact: true })
      if (await toggle.isVisible()) await toggle.click()
      await expect(page.getByRole('button', { name: 'Show results' })).toBeVisible()
    },
  },
  {
    name: 'report page',
    role: 'admin',
    path: '/admin/reports',
    ready: async (page) => {
      await page.getByRole('button', { name: 'Run report' }).first().click()
      await expect(page.getByRole('table')).toBeVisible()
    },
  },
]

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() =>
    Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.documentElement.clientWidth,
    ),
  )
}

/** Visible controls smaller than 44 by 44 CSS pixels (WCAG 2.1 AA target size, spec 06). */
async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const selector =
      'button, a.btn, select, textarea, input:not([type=checkbox]):not([type=radio]):not([type=hidden]), nav a'
    const found: string[] = []
    for (const element of document.querySelectorAll<HTMLElement>(selector)) {
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      const onScreen =
        rect.right > 0 && rect.left < window.innerWidth && rect.width > 0 && rect.height > 0
      if (!onScreen || style.visibility === 'hidden' || style.display === 'none') continue
      if (rect.width < 43.5 || rect.height < 43.5) {
        const label = (element.getAttribute('aria-label') ?? element.textContent ?? '')
          .trim()
          .slice(0, 40)
        found.push(
          `${element.tagName.toLowerCase()} "${label}" is ${Math.round(rect.width)}x${Math.round(rect.height)}`,
        )
      }
    }
    return found
  })
}

async function checkNavigation(page: Page) {
  const width = page.viewportSize()?.width ?? 0
  const menuButton = page.getByRole('button', { name: 'Open menu' })
  const nav = page.getByRole('navigation', { name: 'Main navigation' })
  if (width < 640) {
    await expect(menuButton, 'phones keep the navigation behind a menu button').toBeVisible()
  } else if (width >= 1024) {
    await expect(nav, 'desktops show the navigation all the time').toBeVisible()
    await expect(menuButton).toBeHidden()
  }
}

async function keepScreenshot(page: Page, testInfo: TestInfo, name: string) {
  const path = testInfo.outputPath(`${name.replace(/[^a-z0-9]+/gi, '-')}.png`)
  await page.screenshot({ path, fullPage: true })
  await testInfo.attach(name, { path, contentType: 'image/png' })
}

for (const scenario of SCENARIOS) {
  test(scenario.name, async ({ page }, testInfo) => {
    await mockApi(page, scenario.role)
    await page.goto(scenario.path)
    await scenario.ready(page)

    expect(await horizontalOverflow(page), 'the page scrolls sideways').toBeLessThanOrEqual(0)
    expect(await smallTargets(page), 'controls smaller than 44x44 px').toEqual([])
    if (scenario.role) await checkNavigation(page)
    await keepScreenshot(page, testInfo, scenario.name)
  })
}

// Acceptance criterion 1: no horizontal scrolling at any width from 320 px.
test('narrowest supported width (320 px)', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone-small-360x640', 'run once')
  await page.setViewportSize({ width: 320, height: 640 })
  await mockApi(page, 'workhost')
  await page.goto('/workhost/search')
  await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
  expect(await horizontalOverflow(page), 'the page scrolls sideways').toBeLessThanOrEqual(0)
})
