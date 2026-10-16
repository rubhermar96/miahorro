import { afterEach, describe, expect, it, vi } from 'vitest'

import { applyTheme, getThemePreference, setThemePreference } from './theme'

afterEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.restoreAllMocks()
})

describe('theme preference', () => {
  it('defaults to the system theme', () => {
    expect(getThemePreference()).toBe('system')
  })

  it('saves and applies an explicit theme', () => {
    setThemePreference('dark')

    expect(getThemePreference()).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('removes the override when going back to the system theme', () => {
    applyTheme('light')
    applyTheme('system')

    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('ignores invalid saved values', () => {
    localStorage.setItem('miahorro.theme', 'purple')

    expect(getThemePreference()).toBe('system')
  })

  it('still applies the theme when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    setThemePreference('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
