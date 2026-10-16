import type { ReactNode } from 'react'

/** Highlight the query's words inside a full transcript. */
export function highlightTerms(text: string, query: string): ReactNode {
  const words = query
    .replace(/["()-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 2 && w.toLowerCase() !== 'or')
    .map((w) => w.replace(/[.*+?^${}|[\]\\]/g, '\\$&'))
  if (!words.length) return text
  const re = new RegExp(`(${words.join('|')})`, 'gi')
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
