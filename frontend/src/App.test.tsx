import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './services/api'
import { facets, stats, topics, transcript } from './test/fixtures'

vi.mock('./services/api', () => ({
  getStats: vi.fn(), getFacets: vi.fn(), searchTranscripts: vi.fn(), getTranscript: vi.fn(), ask: vi.fn(),
  getInterviewTopics: vi.fn(), getInterviewSession: vi.fn(), interviewNext: vi.fn(), interviewAnswer: vi.fn(),
  getInterviewReport: vi.fn(), getSimilarQuestions: vi.fn(),
}))
const m = vi.mocked(api)

beforeEach(() => {
  m.getStats.mockResolvedValue(stats)
  m.getFacets.mockResolvedValue(facets())
  m.searchTranscripts.mockResolvedValue({ total: 1, hits: [{ ...transcript(), snippet: '', rank: null }] })
  m.getTranscript.mockResolvedValue(transcript())
  m.getInterviewTopics.mockResolvedValue(topics)
})

it('switches tabs by hash, opens a transcript, toggles the theme and shows the dedication', async () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Dholpur House' })).toBeInTheDocument()
  expect(screen.getByText('UPSC interview prep from real Personality Test transcripts')).toBeInTheDocument()
  expect(screen.getByText(/In respect for every honest public servant/)).toBeInTheDocument()

  await userEvent.click(await screen.findByText('Static'))
  expect(await screen.findByRole('button', { name: 'Original text' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByRole('button', { name: 'Original text' })).toBeNull()

  await userEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }))
  expect(document.documentElement).toHaveClass('dark')
  await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
  expect(document.documentElement).not.toHaveClass('dark')

  window.location.hash = '#interview'
  window.dispatchEvent(new HashChangeEvent('hashchange'))
  expect(await screen.findByText('Practise with the board')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Interview' })).toHaveAttribute('aria-current', 'page')

  window.location.hash = '#ask'
  window.dispatchEvent(new HashChangeEvent('hashchange'))
  expect(await screen.findByRole('button', { name: 'Close Ask AI' })).toBeInTheDocument()
})

it('warns while the first load is still running, and survives a stats failure', async () => {
  m.getStats.mockResolvedValueOnce({ ...stats, transcripts: 0 })
  const { unmount } = render(<App />)
  expect(await screen.findByText(/still being loaded/)).toBeInTheDocument()
  unmount()
  m.getStats.mockRejectedValueOnce(new Error('down'))
  render(<App />)
  expect(await screen.findByText('Static')).toBeInTheDocument()
})
