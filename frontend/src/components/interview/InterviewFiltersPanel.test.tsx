import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { expect, it } from 'vitest'
import { stats, topics } from '../../test/fixtures'
import type { InterviewFilters } from '../../types'
import { InterviewFiltersPanel } from './InterviewFiltersPanel'

it('groups topics and edits every filter', async () => {
  let current: InterviewFilters = { topics: [], board: '', daf: '', question_mode: 'generated' }
  function Harness({ onFilters }: { onFilters: (f: InterviewFilters) => void }) {
    const [f, setF] = useState<InterviewFilters>({ topics: [], board: '', daf: '', question_mode: 'generated' })
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

  await u.click(screen.getByRole('button', { name: 'Real past questions only' }))
  expect(current.question_mode).toBe('real')
  expect(screen.getByText(/No AI needed to ask/)).toBeInTheDocument()
  await u.selectOptions(screen.getByRole('combobox'), 'BB Swain')
  expect(current.board).toBe('BB Swain')
})

it('shows nothing for missing groups', () => {
  render(<InterviewFiltersPanel topics={[]} stats={null} filters={{ topics: [], board: '', daf: '', question_mode: 'generated' }}
    onChange={() => {}} />)
  expect(screen.queryByText('With current affairs')).toBeNull()
  expect(screen.getByText(/New questions written/)).toBeInTheDocument()
})
