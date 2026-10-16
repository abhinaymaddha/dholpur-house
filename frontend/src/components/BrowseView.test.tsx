import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import * as api from '../services/api'
import { facets, meta, stats } from '../test/fixtures'
import { BrowseView } from './BrowseView'

vi.mock('../services/api', () => ({ getFacets: vi.fn(), searchTranscripts: vi.fn(), ask: vi.fn() }))
const search = vi.mocked(api.searchTranscripts)
const getFacets = vi.mocked(api.getFacets)

const hit = (id: string) => ({ ...meta({ id, alias: `Candidate ${id}` }), snippet: `about ⟦${id}⟧`, rank: null })

beforeEach(() => {
  getFacets.mockReset().mockResolvedValue(facets())
  search.mockReset().mockImplementation(async (_q, _f, offset = 0) =>
    ({ total: 30, hits: Array.from({ length: offset ? 6 : 24 }, (_, i) => hit(`u${offset + i}`)) }))
})

it('lists transcripts, searches, sorts, pages and opens one', async () => {
  const onOpen = vi.fn()
  render(<BrowseView stats={stats} askOpen={false} onAskOpen={() => {}} onOpen={onOpen} />)
  expect(await screen.findByText('Candidate u0')).toBeInTheDocument()
  expect(screen.getByText('30 transcripts')).toBeInTheDocument()

  await userEvent.type(screen.getByPlaceholderText(/Search transcripts/), 'gita')
  await waitFor(() => expect(search).toHaveBeenLastCalledWith('gita', expect.anything(), 0, 24, 'relevance'))
  expect(await screen.findByText('30 matching transcripts')).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Sort' }), 'recent')
  await waitFor(() => expect(search).toHaveBeenLastCalledWith('gita', expect.anything(), 0, 24, 'recent'))

  await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
  expect(await screen.findByText('Candidate u29')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull()

  await userEvent.click(screen.getByText('Candidate u3'))
  expect(onOpen).toHaveBeenCalledWith('u3', 'gita')

  await userEvent.click(screen.getByRole('button', { name: 'Clear search' }))
  await waitFor(() => expect(search).toHaveBeenLastCalledWith('', expect.anything(), 0, 24, 'relevance'))
})

it('shows active filter chips that can be removed or cleared', async () => {
  render(<BrowseView stats={stats} askOpen={false} onAskOpen={() => {}} onOpen={() => {}} />)
  await screen.findByText('Candidate u0')
  const u = userEvent.setup()
  await u.click(screen.getByRole('button', { name: /^CSE 2024\s*1$/ }))
  await u.click(screen.getByRole('button', { name: /^Engineering\s*2$/ }))
  await u.click(screen.getByRole('button', { name: /^Mathematics\s*1$/ }))
  await u.click(screen.getByRole('button', { name: /^State 1\s*8$/ }))
  await u.click(screen.getByRole('button', { name: /^Economy\s*3$/ }))
  await u.click(screen.getByRole('checkbox'))
  await u.click(screen.getByRole('button', { name: /^IFoS\s*1$/ }))
  await u.click(screen.getAllByRole('button', { name: /^Sanjay Verma\s*1$/ })[1])
  for (const label of ['CSE 2024', 'Sanjay Verma', 'IFoS', 'Engineering', 'Optional: Mathematics', 'State 1', 'Economy', 'PT marks reported']) {
    expect(screen.getAllByRole('button', { name: label }).length).toBeGreaterThan(0)
  }
  await u.click(screen.getByRole('button', { name: 'Optional: Mathematics' }))
  expect(screen.queryByRole('button', { name: 'Optional: Mathematics' })).toBeNull()
  await u.click(screen.getByRole('button', { name: 'Clear all' }))
  expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
  await u.click(screen.getByRole('button', { name: /Filters/ }))
})

it('removes each chip on its own', async () => {
  render(<BrowseView stats={stats} askOpen={false} onAskOpen={() => {}} onOpen={() => {}} />)
  await screen.findByText('Candidate u0')
  const u = userEvent.setup()
  await u.click(screen.getByRole('button', { name: /^BB Swain\s*2$/ }))
  await u.click(screen.getByRole('button', { name: /^Engineering\s*2$/ }))
  await u.click(screen.getByRole('button', { name: /^State 1\s*8$/ }))
  await u.click(screen.getByRole('button', { name: /^Health\s*2$/ }))
  await u.click(screen.getByRole('checkbox'))
  await u.click(screen.getByRole('button', { name: /^IFoS\s*1$/ }))
  for (const label of ['CSE 2025', 'Engineering', 'State 1', 'Health', 'PT marks reported', 'IFoS']) {
    const chips = screen.getAllByRole('button', { name: label })
    await u.click(chips[chips.length - 1])
  }
  expect(screen.queryByRole('button', { name: 'Clear all' })).toBeNull()
})

it('shows the empty state and opens Ask AI with the right scope', async () => {
  search.mockResolvedValue({ total: 0, hits: [] })
  const onAskOpen = vi.fn()
  const { rerender } = render(<BrowseView stats={stats} askOpen={false} onAskOpen={onAskOpen} onOpen={() => {}} />)
  expect(await screen.findByText(/No transcripts match/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Ask AI/ }))
  expect(onAskOpen).toHaveBeenCalledWith(true)
  rerender(<BrowseView stats={stats} askOpen onAskOpen={onAskOpen} onOpen={() => {}} />)
  expect(screen.getByText(/the 0 transcripts matching/)).toBeInTheDocument()
  search.mockResolvedValue({ total: 4, hits: [hit('a')] })
  await userEvent.type(screen.getByPlaceholderText(/Search transcripts/), 'x')
  expect(await screen.findByText(/Answers from all 4 transcripts/)).toBeInTheDocument()
})
