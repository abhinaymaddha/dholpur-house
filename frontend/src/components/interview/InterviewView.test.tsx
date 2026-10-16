import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import * as api from '../../services/api'
import { evaluation, stats, topics, turn } from '../../test/fixtures'
import type { InterviewReport, Turn } from '../../types'
import { InterviewView } from './InterviewView'

vi.mock('../../services/api', () => ({
  getInterviewTopics: vi.fn(), getInterviewSession: vi.fn(), interviewNext: vi.fn(), interviewAnswer: vi.fn(),
  getInterviewReport: vi.fn(), getSimilarQuestions: vi.fn(),
}))
const m = vi.mocked(api)

let turns: Turn[]
beforeEach(() => {
  turns = []
  m.getInterviewTopics.mockReset().mockResolvedValue(topics)
  m.getInterviewSession.mockReset().mockImplementation(async () => turns)
  m.interviewNext.mockReset().mockImplementation(async () => {
    turns = [...turns, turn({ id: turns.length + 1, main_index: turns.length + 1 })]
    return { session_id: 's1', turn: turns[turns.length - 1] }
  })
  m.interviewAnswer.mockReset()
  m.getInterviewReport.mockReset()
  m.getSimilarQuestions.mockReset().mockResolvedValue([
    { id: 9, text: 'Define GDP?', follow_up: 'And GNP?', member: 'Member 1', transcript_id: 'u7', board: 'BB Swain',
      cse_year: 2025, alias: null }])
})

const pickTopicAndStart = async () => {
  await userEvent.click(await screen.findByRole('button', { name: 'Economy' }))
  await userEvent.click(screen.getAllByRole('button', { name: 'Start' })[0])
}

it('runs a coach-mode conversation with feedback, a follow-up and a report', async () => {
  const onOpen = vi.fn()
  render(<InterviewView stats={stats} onOpen={onOpen} />)
  await pickTopicAndStart()
  expect(await screen.findByText('What is GDP?')).toBeInTheDocument()
  expect(screen.getByText(/Asked in CSE 2024 · Sanjay Verma board/)).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: /How have boards asked this/ }))
  expect(await screen.findByText('Define GDP?')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /open transcript/ }))
  expect(onOpen).toHaveBeenCalledWith('u7', '')
  await userEvent.click(screen.getByRole('button', { name: 'Hide' }))
  await userEvent.click(screen.getByText(/view transcript/))
  expect(onOpen).toHaveBeenCalledWith('u1', '')

  m.interviewAnswer.mockImplementation(async () => {
    turns = [{ ...turns[0], answer: 'Output of the economy', mode: 'coach', evaluation: evaluation({ verdict: 'good' }) },
             turn({ id: 2, depth: 1, question: 'Why does it matter?', source: { type: 'followup' } })]
    return { evaluation: evaluation(), next: turns[1] }
  })
  await userEvent.type(screen.getByPlaceholderText(/Answer as you would/), 'Output of the economy{Enter}')
  expect(await screen.findByText('Why does it matter?')).toBeInTheDocument()
  expect(screen.getByText('Follow-up 1 of 2')).toBeInTheDocument()
  expect(screen.getByText('Good enough for a follow-up')).toBeInTheDocument()
  expect(m.interviewAnswer).toHaveBeenCalledWith('s1', 'Output of the economy', 'coach', expect.anything())

  const report: InterviewReport = { answered: 1, skipped: 0, average: 3.25, verdicts: { good: 1, partial: 0, weak: 0 },
    dimensions: { relevance: 4 }, topics: [{ topic: 'Economy', answered: 1, average: 3.25 }], turns: [turns[0]] }
  m.getInterviewReport.mockResolvedValue(report)
  await userEvent.click(screen.getByRole('button', { name: 'Report' }))
  expect(await screen.findByText(/1 answered · 0 skipped · average 3.3\/5/)).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'New' }))
  expect(screen.getByText('Practise with the board')).toBeInTheDocument()
})

it('exam mode hides feedback, and errors are shown', async () => {
  render(<InterviewView stats={stats} onOpen={() => {}} />)
  await userEvent.click(await screen.findByRole('radio', { name: 'Exam Mode' }))
  expect(screen.getByText('Feedback only in the report')).toBeInTheDocument()
  await pickTopicAndStart()
  await screen.findByText('What is GDP?')
  m.interviewAnswer.mockImplementation(async () => {
    turns = [{ ...turns[0], answer: 'A', mode: 'exam', evaluation: evaluation() }]
    return { evaluation: evaluation(), next: turns[0] }
  })
  await userEvent.type(screen.getByPlaceholderText(/Answer as you would/), 'A')
  await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
  expect(await screen.findByText('Exam mode: feedback saved for the report.')).toBeInTheDocument()

  m.interviewNext.mockRejectedValueOnce(new Error('The AI model failed: rate limited'))
  await userEvent.click(screen.getByRole('button', { name: /Next question/ }))
  expect(await screen.findByText('The AI model failed: rate limited')).toBeInTheDocument()
})

it('resumes a saved session and shows every kind of question source', async () => {
  localStorage.setItem('upsc-interview', JSON.stringify({ sessionId: 's9', mode: 'coach', filters: { topics: ['Economy'] } }))
  turns = [
    turn({ id: 1, source: { type: 'generated', angle: 'news', based_on: 'RBI news', url: 'https://n/1', publisher: 'The Hindu' },
      evaluation: { skipped: true } as never }),
    turn({ id: 2, main_index: 2, source: { type: 'generated', angle: 'daf', based_on: 'MBBS' } }),
    turn({ id: 3, main_index: 3, source: { type: 'generated', angle: 'topic' } }),
    turn({ id: 4, main_index: 4, source: { type: 'daf', daf_item: 'Kota' } }),
    turn({ id: 5, main_index: 5, source: { type: 'current', url: 'https://n/2', title: 'Budget', publisher: 'PIB' } }),
  ]
  m.getSimilarQuestions.mockResolvedValue([])
  render(<InterviewView stats={stats} onOpen={() => {}} />)
  expect(await screen.findByText(/from the news: RBI news · The Hindu/)).toBeInTheDocument()
  expect(screen.getByText('Skipped')).toBeInTheDocument()
  expect(screen.getByText('New question · from your DAF: MBBS')).toBeInTheDocument()
  expect(screen.getByText('New question · on the topic')).toBeInTheDocument()
  expect(screen.getByText('From your DAF: Kota')).toBeInTheDocument()
  expect(screen.getByText(/From the news: Budget · PIB/)).toBeInTheDocument()
  await userEvent.click(screen.getAllByRole('button', { name: /How have boards asked this/ })[0])
  expect(await screen.findByText('No similar questions found.')).toBeInTheDocument()
})

it('forgets a session the server no longer has, and survives broken storage', async () => {
  localStorage.setItem('upsc-interview', '{not json')
  m.getInterviewTopics.mockRejectedValue(new Error('down'))
  render(<InterviewView stats={null} onOpen={() => {}} />)
  expect(await screen.findByText('Practise with the board')).toBeInTheDocument()

  localStorage.setItem('upsc-interview', JSON.stringify({ sessionId: 'gone' }))
  m.getInterviewSession.mockRejectedValue(new Error('404'))
  render(<InterviewView stats={null} onOpen={() => {}} />)
  await waitFor(() => expect(JSON.parse(localStorage.getItem('upsc-interview')!).sessionId).toBeNull())
})

it('shows an empty report and the mobile filter toggle', async () => {
  render(<InterviewView stats={stats} onOpen={() => {}} />)
  await pickTopicAndStart()
  await screen.findByText('What is GDP?')
  m.interviewAnswer.mockImplementation(async () => {
    turns = [{ ...turns[0], answer: 'A', mode: 'coach', evaluation: evaluation() }]
    return { evaluation: evaluation(), next: turns[0] }
  })
  await userEvent.type(screen.getByPlaceholderText(/Answer as you would/), 'A{Enter}')
  m.getInterviewReport.mockResolvedValue({ answered: 0, skipped: 0, average: 0, verdicts: { good: 0, partial: 0, weak: 0 },
    dimensions: {}, topics: [], turns: [] })
  await userEvent.click(await screen.findByRole('button', { name: 'Report' }))
  expect(await screen.findByText('Answer a few questions first to see a report.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Filters \(1\)/ }))
})
