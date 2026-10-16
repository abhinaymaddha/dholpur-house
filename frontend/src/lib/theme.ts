export type Theme = 'light' | 'dark'

const KEY = 'theme'

/** The saved choice, else the system preference. index.html applies it before first paint. */
export function currentTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export function setTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // storage unavailable (private window): the choice lasts for this visit only
  }
}
