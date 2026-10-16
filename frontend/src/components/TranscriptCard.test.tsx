import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { meta } from '../test/fixtures'
import { TranscriptCard } from './TranscriptCard'

it('shows the candidate, board, marks, tags and a highlighted snippet', async () => {
  const onOpen = vi.fn()
  const { container } = render(<TranscriptCard t={meta()} snippet="read the ⟦Gita⟧" onOpen={onOpen} />)
  expect(screen.getByText('Static')).toBeInTheDocument()
  expect(screen.getByText('PT 187')).toBeInTheDocument()
  expect(screen.getByText('Optional: Maths')).toBeInTheDocument()
  expect(screen.getByText('Opt: Mathematics')).toBeInTheDocument()
  expect(screen.getByText('+1')).toBeInTheDocument()                 // 5 topics, 4 shown
  expect(container.querySelector('mark')).toHaveTextContent('Gita')
  await userEvent.click(screen.getByRole('button'))
  expect(onOpen).toHaveBeenCalled()
})

it('handles an anonymous IFoS candidate without marks or DAF', () => {
  render(<TranscriptCard t={meta({ alias: null, exam: 'IFoS', pt_marks: null, daf: null, question_count: 0,
    optional_tag: null, interview_date: null, optional_subject: null })} onOpen={() => {}} />)
  expect(screen.getByText('Anonymous candidate')).toBeInTheDocument()
  expect(screen.getByText('CSE 2024 · IFoS')).toBeInTheDocument()
  expect(screen.queryByText(/PT /)).toBeNull()
  expect(screen.queryByText(/DAF:/)).toBeNull()
})
