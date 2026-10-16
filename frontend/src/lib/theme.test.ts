import { describe, expect, it, vi } from 'vitest'
import { currentTheme, setTheme } from './theme'

describe('theme', () => {
  it('reads and writes the dark class and remembers the choice', () => {
    expect(currentTheme()).toBe('light')
    setTheme('dark')
    expect(document.documentElement).toHaveClass('dark')
    expect(currentTheme()).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    setTheme('light')
    expect(currentTheme()).toBe('light')
  })
  it('still switches when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('private mode') })
    setTheme('dark')
    expect(currentTheme()).toBe('dark')
  })
})
