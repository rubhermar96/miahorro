export type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'miahorro.theme'
const PREFERENCES: readonly ThemePreference[] = ['system', 'light', 'dark']

/** Saved preference; falls back to the system theme if storage is unavailable or invalid. */
export function getThemePreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return PREFERENCES.find((preference) => preference === saved) ?? 'system'
  } catch {
    return 'system'
  }
}

/** Apply a preference to the document: "system" defers to prefers-color-scheme in CSS. */
export function applyTheme(preference: ThemePreference): void {
  const root = document.documentElement
  if (preference === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = preference
  }
}

export function setThemePreference(preference: ThemePreference): void {
  applyTheme(preference)
  try {
    localStorage.setItem(STORAGE_KEY, preference)
  } catch {
    // Private mode or blocked storage: the theme still applies for this session.
  }
}
