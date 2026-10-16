import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom has no layout: give elements a no-op scrollIntoView.
Element.prototype.scrollIntoView = function scrollIntoView() {}

afterEach(() => {
  cleanup()
  localStorage.clear()
  document.documentElement.className = ''
  window.location.hash = ''
})
