import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { formatDate, highlightTerms } from './format'
import { Answer, Snippet } from './text'

describe('Snippet', () => {
  it('turns highlight markers into <mark> without injecting HTML', () => {
    const { container } = render(<p><Snippet text={'before ⟦dharma⟧ and ⟦gita⟧ <b>x</b>'} /></p>)
    expect([...container.querySelectorAll('mark')].map((m) => m.textContent)).toEqual(['dharma', 'gita'])
    expect(container.querySelector('b')).toBeNull()
    expect(container.textContent).toBe('before dharma and gita <b>x</b>')
  })
})

describe('highlightTerms', () => {
  it('marks query words, ignoring short words, OR and regex characters', () => {
    const { container } = render(<p>{highlightTerms('Repo rate and the RBI (c++)', '"repo" OR rbi c++ an')}</p>)
    expect([...container.querySelectorAll('mark')].map((m) => m.textContent)).toEqual(['Repo', 'RBI', 'c++'])
  })
  it('returns the text unchanged when nothing is searchable', () => {
    expect(highlightTerms('plain', 'or a')).toBe('plain')
  })
})

describe('Answer', () => {
  it('renders headings, lists, bold and clickable citations', async () => {
    const onCite = vi.fn()
    const text = '## Summary\nBoards ask **often** about it [S1].\n- first 【S2】\n- second\n1. one\n2. two\n\nEnd.'
    const { container } = render(<Answer text={text} onCite={onCite} />)
    expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
    expect(container.querySelector('strong')).toHaveTextContent('often')
    expect(container.querySelectorAll('ul li')).toHaveLength(2)
    expect(container.querySelectorAll('ol li')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'S2' }))
    expect(onCite).toHaveBeenCalledWith(2)
  })
})

it('formats dates for India', () => {
  expect(formatDate('2025-01-11T09:00:00')).toBe('11 Jan 2025')
})
