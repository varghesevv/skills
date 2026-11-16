import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ThemeChoice from './ThemeChoice'
import { applyTheme, savedTheme } from './theme'

afterEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.restoreAllMocks()
})

describe('the theme choice', () => {
  it('is "system" until one is chosen', () => {
    expect(savedTheme()).toBe('system')
  })

  it('sets and remembers dark, and goes back to the system setting', () => {
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(savedTheme()).toBe('dark')
    applyTheme('system')
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(savedTheme()).toBe('system')
  })

  it('ignores a saved value it does not know', () => {
    localStorage.setItem('skills.theme', 'purple')
    expect(savedTheme()).toBe('system')
  })

  it('still applies for this visit when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    applyTheme('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(savedTheme()).toBe('system')
  })

  it('offers three choices and applies the one picked', async () => {
    render(<ThemeChoice />)
    expect(screen.getByRole('radio', { name: 'Same as my device' })).toBeChecked()
    await userEvent.click(screen.getByRole('radio', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked()
  })
})
