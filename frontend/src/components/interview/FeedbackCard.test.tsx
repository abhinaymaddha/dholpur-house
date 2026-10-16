import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { evaluation } from '../../test/fixtures'
import { FeedbackCard, VerdictPill } from './FeedbackCard'

it('shows verdict, scores, quoted issues, strengths and what was missing', () => {
  render(<FeedbackCard e={evaluation()} followUpNext={false} />)
  expect(screen.getByText('Partial · 3.3/5')).toBeInTheDocument()
  expect(screen.getByText('No follow-up: moving on')).toBeInTheDocument()
  expect(screen.getByText('it is always good')).toBeInTheDocument()
  expect(screen.getByText('Missing from your answer')).toBeInTheDocument()
  expect(screen.getByText('One-sided')).toBeInTheDocument()
  expect(screen.getByText('Structure')).toBeInTheDocument()          // unknown issue types fall back
  expect(screen.getByText('Clear opening')).toBeInTheDocument()
  expect(screen.getByText('Federal angle')).toBeInTheDocument()
  expect(screen.getByText('Define the term')).toBeInTheDocument()
  expect(screen.getByText('balance').nextSibling?.firstChild).toHaveClass('bg-rose-500')
})

it('handles good answers and old evaluations without issues or strengths', () => {
  const { rerender } = render(<FeedbackCard e={evaluation({ verdict: 'good', issues: undefined, strengths: undefined,
    missing_points: [], model_answer_points: [] })} followUpNext />)
  expect(screen.getByText('Good enough for a follow-up')).toBeInTheDocument()
  expect(screen.queryByText('Where it went wrong')).toBeNull()
  rerender(<FeedbackCard e={evaluation({ verdict: 'good' })} followUpNext={false} />)
  expect(screen.getByText('Moving to a new question')).toBeInTheDocument()
})

it('renders a verdict without an average', () => {
  render(<VerdictPill verdict="weak" />)
  expect(screen.getByText('Weak')).toBeInTheDocument()
})
