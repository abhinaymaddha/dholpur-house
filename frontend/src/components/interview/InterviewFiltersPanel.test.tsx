import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { stats, topics } from '../../test/fixtures'
import type { InterviewFilters } from '../../types'
import { InterviewFiltersPanel } from './InterviewFiltersPanel'

it('groups topics and edits every filter', async () => {
  let current: InterviewFilters = { topics: [], board: '', daf: '', question_mode: 'generated', plan: 'topics', length: 10 }
  function Harness({ onFilters }: { onFilters: (f: InterviewFilters) => void }) {
    const [f, setF] = useState<InterviewFilters>({ topics: [], board: '', daf: '', question_mode: 'generated', plan: 'topics', length: 10 })
    onFilters(f)
    return <InterviewFiltersPanel topics={topics} stats={stats} filters={f} onChange={setF} />
  }
  render(<Harness onFilters={(f) => { current = f }} />)
  const u = userEvent.setup()
  expect(screen.getByText('With current affairs')).toBeInTheDocument()
  expect(screen.getByText('Questions on your own background')).toBeInTheDocument()
  expect(screen.getByRole('option', { name: 'BB Swain' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Unknown' })).toBeNull()

  await u.click(screen.getByRole('button', { name: 'Economy' }))
  await u.click(screen.getByRole('button', { name: 'DAF & Background' }))
  expect(current.topics).toEqual(['Economy', 'DAF & Background'])
  expect(screen.getByText('Needed for “Your DAF” questions.')).toBeInTheDocument()
  await u.type(screen.getByPlaceholderText(/Hometown/), 'Kota')
  expect(current.daf).toBe('Kota')
  expect(screen.getByText(/Personalises questions/)).toBeInTheDocument()
  await u.click(screen.getByRole('button', { name: 'Economy' }))
  expect(current.topics).toEqual(['DAF & Background'])

  await u.click(screen.getByRole('radio', { name: 'Real past questions only' }))
  expect(current.question_mode).toBe('real')
  expect(screen.getByText(/No AI needed to ask/)).toBeInTheDocument()
  await u.selectOptions(screen.getByRole('combobox'), 'BB Swain')
  expect(current.board).toBe('BB Swain')
})

it('a full interview hides the topics and offers a length', async () => {
  let current: InterviewFilters | null = null
  function Harness() {
    const [f, setF] = useState<InterviewFilters>({ topics: [], board: '', daf: '', question_mode: 'generated', plan: 'topics', length: 10 })
    current = f
    return <InterviewFiltersPanel topics={topics} stats={stats} filters={f} onChange={setF} />
  }
  render(<Harness />)
  const u = userEvent.setup()
  expect(screen.getByText('Only the topics you pick, in turn.')).toBeInTheDocument()
  await u.click(screen.getByRole('radio', { name: 'Full interview' }))
  expect(current!.plan).toBe('full')
  expect(screen.queryByText('With current affairs')).toBeNull()
  expect(screen.getByText(/four members choose the questions/)).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: 'Short · 10' })).toHaveAttribute('aria-checked', 'true')
  await u.click(screen.getByRole('radio', { name: 'Long · 30' }))
  expect(current!.length).toBe(30)
  expect(screen.getByText(/the board opens with general questions about you/)).toBeInTheDocument()
  await u.type(screen.getByPlaceholderText(/Hometown/), 'Kota')
  expect(screen.queryByText(/the board opens with general questions/)).toBeNull()
})

it('shows nothing for missing groups', () => {
  render(<InterviewFiltersPanel topics={[]} stats={null} filters={{ topics: [], board: '', daf: '', question_mode: 'generated', plan: 'topics', length: 10 }}
    onChange={() => {}} />)
  expect(screen.queryByText('With current affairs')).toBeNull()
  expect(screen.getByText(/New questions written/)).toBeInTheDocument()
})
