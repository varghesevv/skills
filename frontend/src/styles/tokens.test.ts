import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// The colour tokens of docs/design-system.md, section 1.1: every pair that carries text or a
// control edge must reach its WCAG 2.2 contrast, in both themes, and the dark values written
// twice in global.css (media query and data-theme) must be the same.

const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')

function block(start: string): Record<string, string> {
  const at = css.indexOf(start)
  if (at < 0) throw new Error(`no block ${start}`)
  const body = css.slice(css.indexOf('{', at) + 1, css.indexOf('}', at))
  const tokens: Record<string, string> = {}
  for (const match of body.matchAll(/(--[a-z-]+):\s*([^;]+);/g)) tokens[match[1]] = match[2].trim()
  return tokens
}

const light = block(':root {\n  color-scheme: light dark;')
const dark = block(":root[data-theme='dark']")
const media = block(":root:not([data-theme='light'])")

function luminance(hex: string): number {
  const channel = (i: number) => {
    const v = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2)
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// [foreground, background, minimum]: text 4.5, large text and UI parts 3.
const PAIRS: [string, string, number][] = [
  ['--ink', '--bg', 4.5],
  ['--ink', '--surface', 4.5],
  ['--ink', '--accent-bg', 4.5],
  ['--muted', '--bg', 4.5],
  ['--muted', '--surface', 4.5],
  ['--muted', '--accent-bg', 4.5],
  ['--accent-ink', '--accent', 4.5],
  ['--accent-ink', '--accent-hover', 4.5],
  ['--accent', '--bg', 4.5],
  ['--accent', '--surface', 4.5],
  ['--accent-bg-ink', '--accent-bg', 4.5],
  ['--success', '--success-bg', 4.5],
  ['--success', '--surface', 4.5],
  ['--danger', '--surface', 4.5],
  ['--danger', '--danger-bg', 4.5],
  ['--line-strong', '--bg', 3],
  ['--line-strong', '--surface', 3],
  ['--focus', '--bg', 3],
  ['--focus', '--surface', 3],
  ['--focus', '--accent-bg', 3],
]

describe.each([
  ['light', light],
  ['dark', dark],
])('the %s tokens', (_name, tokens) => {
  it.each(PAIRS)('%s on %s reaches %s:1', (fg, bg, minimum) => {
    expect(contrast(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(minimum)
  })
})

describe('the dark tokens', () => {
  it('are the same for the system setting and for the chosen setting', () => {
    expect(media).toEqual(Object.fromEntries(Object.entries(dark).filter(([k]) => k in media)))
    expect(Object.keys(media).sort()).toEqual(Object.keys(dark).sort())
  })

  it('define every token the light block does, apart from sizes and the font', () => {
    const colours = Object.keys(light).filter(
      (name) => !['--radius', '--topbar-height', '--font'].includes(name),
    )
    expect(Object.keys(dark).sort()).toEqual(colours.sort())
  })
})
