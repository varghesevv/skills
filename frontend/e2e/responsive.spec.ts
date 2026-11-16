import AxeBuilder from '@axe-core/playwright'
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
    name: 'landing',
    role: null,
    path: '/',
    ready: async (page) => {
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    },
  },
  {
    name: 'member home',
    role: 'searcher',
    path: '/member',
    ready: async (page) => {
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    },
  },
  {
    name: 'member sign in',
    role: null,
    path: '/sign-in',
    ready: async (page) => {
      await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    },
  },
  {
    name: 'member sign up',
    role: null,
    path: '/sign-up',
    ready: async (page) => {
      await expect(page.getByRole('heading', { name: 'Join' })).toBeVisible()
      await expect(page.getByLabel('New password')).toBeVisible()
    },
  },
  {
    name: 'form page (profile)',
    role: 'provider',
    path: '/member/profile',
    ready: async (page) => {
      await expect(page.getByLabel('Rate per hour')).toBeVisible()
    },
  },
  {
    name: 'search',
    role: 'searcher',
    path: '/member/search',
    ready: async (page) => {
      await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
    },
  },
  {
    name: 'search with the filter panel open',
    role: 'searcher',
    path: '/member/search',
    ready: async (page) => {
      await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
      const toggle = page.getByRole('button', { name: 'Filters', exact: true })
      if (await toggle.isVisible()) {
        await toggle.click()
        await expect(page.getByRole('button', { name: 'Show results' }).first()).toBeVisible()
      } else {
        // From 1024 px the filters apply as they change, so there is no Show results button.
        await expect(page.getByRole('button', { name: 'Clear filters' }).first()).toBeVisible()
      }
    },
  },
  {
    name: 'report page',
    role: 'owner',
    path: '/member/reports',
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
    await keepScreenshot(page, testInfo, scenario.name)
  })
}

// docs/design-system.md, 2.2: on a phone the links sit behind one Menu button, and every group
// opens without a sideways scroll, with targets of 44 px.
test('the phone menu of an owner, open', async ({ page }, testInfo) => {
  test.skip(!['phone-small-360x640', 'phone-390x844'].includes(testInfo.project.name), 'phones')
  await mockApi(page, 'owner')
  await page.goto('/member')
  await page.getByRole('button', { name: 'Menu' }).click()
  await expect(page.getByRole('link', { name: 'Applicants' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Number views' })).toBeVisible()
  expect(await horizontalOverflow(page), 'the page scrolls sideways').toBeLessThanOrEqual(0)
  expect(await smallTargets(page), 'controls smaller than 44x44 px').toEqual([])
  await keepScreenshot(page, testInfo, 'phone menu open')
})

// On a tablet or desktop a group opens as a floating list.
test('a group menu of the top bar opens', async ({ page }, testInfo) => {
  test.skip(['phone-small-360x640', 'phone-390x844'].includes(testInfo.project.name), 'wider')
  await mockApi(page, 'owner')
  await page.goto('/member')
  await page.getByRole('button', { name: 'Leader' }).click()
  await expect(page.getByRole('link', { name: 'Applicants' })).toBeVisible()
  expect(await horizontalOverflow(page), 'the page scrolls sideways').toBeLessThanOrEqual(0)
  await keepScreenshot(page, testInfo, 'group menu open')
})

// Section 4, step 1: no automatically detectable accessibility problem (contrast included) in
// either theme, on the pages that carry the most of the design.
for (const theme of ['light', 'dark'] as const) {
  for (const target of [
    { name: 'search', role: 'searcher' as Role, path: '/member/search' },
    { name: 'member home', role: 'provider' as Role, path: '/member' },
    { name: 'account', role: 'searcher' as Role, path: '/member/account' },
  ]) {
    test(`axe finds nothing on ${target.name} in the ${theme} theme`, async ({
      page,
    }, testInfo) => {
      test.skip(testInfo.project.name !== 'desktop-1440x900', 'run once')
      await page.emulateMedia({ colorScheme: theme })
      await mockApi(page, target.role)
      await page.goto(target.path)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
      expect(
        result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(' | ')}`),
      ).toEqual([])
    })
  }
}

// A saved choice wins over the system setting, with no flash of the other theme.
test('a saved dark choice is applied before the first paint', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1440x900', 'run once')
  await page.emulateMedia({ colorScheme: 'light' })
  await page.addInitScript(() => localStorage.setItem('skills.theme', 'dark'))
  await mockApi(page, null)
  await page.goto('/')
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe('dark')
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(
    'rgb(21, 21, 23)',
  )
})

// Acceptance criterion 1: no horizontal scrolling at any width from 320 px.
test('narrowest supported width (320 px)', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'phone-small-360x640', 'run once')
  await page.setViewportSize({ width: 320, height: 640 })
  await mockApi(page, 'searcher')
  await page.goto('/member/search')
  await expect(page.getByText('40 freelancer(s) found')).toBeVisible()
  expect(await horizontalOverflow(page), 'the page scrolls sideways').toBeLessThanOrEqual(0)
})
