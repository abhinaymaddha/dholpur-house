import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../services/api'
import { evaluation, stats, topics, turn } from '../../test/fixtures'
import { FakeRecognition, installSpeech } from '../../test/speech'
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
  // These tests practise chosen topics in Coach mode; the full-interview defaults have their own tests below.
  localStorage.setItem('upsc-interview', JSON.stringify({ mode: 'coach', voice: false, filters: { plan: 'topics' } }))
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
  expect(m.interviewAnswer).toHaveBeenCalledWith('s1', 'Output of the economy', 'coach', expect.anything(), false)

  const report: InterviewReport = { answered: 1, pending: 0, failed: 0, skipped: 0, average: 3.25, verdicts: { good: 1, partial: 0, weak: 0 },
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
    turn({ id: 6, main_index: 6, source: { type: 'opening' } }),
  ]
  m.getSimilarQuestions.mockResolvedValue([])
  render(<InterviewView stats={stats} onOpen={() => {}} />)
  expect(await screen.findByText(/from the news: RBI news · The Hindu/)).toBeInTheDocument()
  expect(screen.getByText('Skipped')).toBeInTheDocument()
  expect(screen.getByText('New question · from your DAF: MBBS')).toBeInTheDocument()
  expect(screen.getByText('New question · on the topic')).toBeInTheDocument()
  expect(screen.getByText('From your DAF: Kota')).toBeInTheDocument()
  expect(screen.getByText(/From the news: Budget · PIB/)).toBeInTheDocument()
  expect(screen.getByText("The board's opening question")).toBeInTheDocument()
  await userEvent.click(screen.getAllByRole('button', { name: /How have boards asked this/ })[0])
  expect(await screen.findByText('No similar questions found.')).toBeInTheDocument()
})

it('forgets a session the server no longer has, and survives broken storage', async () => {
  localStorage.setItem('upsc-interview', '{not json')
  m.getInterviewTopics.mockRejectedValue(new Error('down'))
  render(<InterviewView stats={null} onOpen={() => {}} />)
  expect(await screen.findByText('Face the board')).toBeInTheDocument()

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
  m.getInterviewReport.mockResolvedValue({ answered: 0, pending: 0, failed: 0, skipped: 0, average: 0, verdicts: { good: 0, partial: 0, weak: 0 },
    dimensions: {}, topics: [], turns: [] })
  await userEvent.click(await screen.findByRole('button', { name: 'Report' }))
  expect(await screen.findByText('Answer a few questions first to see a report.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: /Filters \(1\)/ }))
})

describe('voice mode', () => {
  afterEach(() => vi.unstubAllGlobals())

  const answerWith = (answer: string, mode: 'coach' | 'exam') => m.interviewAnswer.mockImplementation(async () => {
    turns = [{ ...turns[0], answer, mode, evaluation: evaluation() }, turn({ id: 2, main_index: 2, question: 'Next one?' })]
    return { evaluation: evaluation(), next: turns[1] }
  })

  it('reads the question aloud, then listens, and sends the spoken answer as spoken', async () => {
    const speech = installSpeech()
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: /Voice/ }))
    await pickTopicAndStart()
    await screen.findByText('What is GDP?')
    expect(speech.spoken()).toEqual(['What is GDP?'])
    expect(screen.getByText('The board is asking…')).toBeInTheDocument()

    act(() => speech.finish())
    expect(FakeRecognition.last.started).toBe(true)
    expect(screen.getByPlaceholderText('Listening… speak your answer')).toBeInTheDocument()
    expect(screen.getByText(/only the text reaches Dholpur House/)).toBeInTheDocument()
    act(() => FakeRecognition.last.say(['Output of the economy', true]))
    expect(screen.getByLabelText('Your answer')).toHaveValue('Output of the economy')

    answerWith('Output of the economy', 'coach')
    await userEvent.click(screen.getByRole('button', { name: 'Send answer' }))
    expect(m.interviewAnswer).toHaveBeenCalledWith('s1', 'Output of the economy', 'coach', expect.anything(), true)
    await screen.findByText('Next one?')
    expect(speech.spoken()).toEqual(['What is GDP?', 'Next one?'])
    expect(JSON.parse(localStorage.getItem('upsc-interview')!).voice).toBe(true)

    await userEvent.click(screen.getByRole('button', { name: /Voice/ }))     // off: stops reading and listening
    expect(speech.synth.cancel).toHaveBeenCalled()
    act(() => speech.finish())
    expect(screen.queryByPlaceholderText('Listening… speak your answer')).not.toBeInTheDocument()
  })

  it('in exam mode a spoken answer is locked; typing stops the mic; mic errors are shown', async () => {
    installSpeech()
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(await screen.findByRole('radio', { name: 'Exam Mode' }))
    await pickTopicAndStart()
    await screen.findByText('What is GDP?')

    await userEvent.type(screen.getByLabelText('Your answer'), 'Typed')
    await userEvent.click(screen.getByRole('button', { name: 'Speak your answer' }))
    expect(screen.getByRole('button', { name: 'Stop speaking' })).toHaveAttribute('aria-pressed', 'true')
    act(() => FakeRecognition.last.say(['and spoken', true]))
    const box = screen.getByLabelText('Your answer')
    expect(box).toHaveValue('Typed and spoken')
    await userEvent.click(screen.getByRole('button', { name: 'Stop speaking' }))
    expect(box).toHaveAttribute('readonly')
    expect(screen.getByText(/a spoken answer can't be edited/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: 'Coach Mode' }))
    await userEvent.click(screen.getByRole('button', { name: 'Speak your answer' }))
    await userEvent.type(box, '!')                 // typing takes over from the microphone
    expect(screen.getByRole('button', { name: 'Speak your answer' })).toBeInTheDocument()
    expect(box).toHaveValue('Typed and spoken!')

    await userEvent.click(screen.getByRole('button', { name: 'Speak your answer' }))
    act(() => FakeRecognition.last.fail('not-allowed'))
    expect(screen.getByText(/Microphone access is blocked/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'New' }))
    expect(screen.getByText('Practise with the board')).toBeInTheDocument()
  })

  it('reads any question aloud on request, and stops it to speak', async () => {
    const speech = installSpeech()
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await pickTopicAndStart()
    await screen.findByText('What is GDP?')
    expect(speech.spoken()).toEqual([])                 // voice mode is off
    await userEvent.click(screen.getByRole('button', { name: 'Read the question aloud' }))
    expect(speech.spoken()).toEqual(['What is GDP?'])
    await userEvent.click(screen.getByRole('button', { name: 'Speak your answer' }))
    expect(FakeRecognition.last.started).toBe(true)
    act(() => speech.finish())
    expect(screen.queryByText('The board is asking…')).not.toBeInTheDocument()
  })

  it('without speech recognition: questions are read, answers typed', async () => {
    const speech = installSpeech({ listen: false })
    localStorage.setItem('upsc-interview', JSON.stringify({ voice: true, filters: { topics: ['Economy'] } }))
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(screen.getAllByRole('button', { name: 'Start' })[0])
    await screen.findByText('What is GDP?')
    act(() => speech.finish())
    expect(screen.queryByRole('button', { name: 'Speak your answer' })).not.toBeInTheDocument()
    expect(screen.getByText(/can't transcribe speech/)).toBeInTheDocument()
  })

  it('with recognition but no speech synthesis, the microphone opens straight away', async () => {
    vi.stubGlobal('webkitSpeechRecognition', FakeRecognition)
    FakeRecognition.instances = []
    localStorage.setItem('upsc-interview', JSON.stringify({ voice: true, filters: { topics: ['Economy'] } }))
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(screen.getAllByRole('button', { name: 'Start' })[0])
    await screen.findByText('What is GDP?')
    expect(FakeRecognition.last.started).toBe(true)
    expect(screen.queryByRole('button', { name: 'Read the question aloud' })).not.toBeInTheDocument()
  })

  it('has no voice controls where the browser has no speech support', async () => {
    localStorage.setItem('upsc-interview', JSON.stringify({ voice: true }))
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await screen.findByText('Face the board')
    expect(screen.queryByRole('button', { name: /Voice/ })).not.toBeInTheDocument()
  })
})

describe('full interview', () => {
  afterEach(() => vi.unstubAllGlobals())

  const asked = (n: number, by: string) => turn({ id: n, main_index: n, question: `Question ${n}?`,
    source: { type: 'past', asked_by: by, transcript_id: 'u1', board: 'B', cse_year: 2024 } })

  it('starts without topics, in Exam mode with voice, and ends with thanks and the report', async () => {
    localStorage.clear()
    const speech = installSpeech()
    const next = [asked(1, 'Chairperson'), asked(10, 'Member 2')]
    m.interviewNext.mockImplementation(async () => {
      turns = [...turns.map((t) => ({ ...t, evaluation: { skipped: true } as never })), next.shift()!]
      return { session_id: 's1', turn: turns[turns.length - 1] }
    })
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    expect(await screen.findByText('Face the board')).toBeInTheDocument()
    expect(screen.getByText(/A full interview of 10 questions/)).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Exam Mode' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('button', { name: /Voice/ })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getAllByRole('button', { name: 'Start' })[0])
    expect(await screen.findByText('Question 1?')).toBeInTheDocument()
    expect(screen.getByText('Chairperson · Economy')).toBeInTheDocument()
    expect(screen.getByTitle('Chairperson')).toHaveTextContent('C')
    expect(screen.getByText('Question 1 of 10')).toBeInTheDocument()
    expect(speech.spoken()).toEqual(['Question 1?'])

    await userEvent.click(screen.getByRole('button', { name: /Next question/ }))
    expect(await screen.findByText('Question 10?')).toBeInTheDocument()
    expect(screen.getByTitle('Member 2')).toHaveTextContent('M2')
    expect(screen.getByText('Question 10 of 10')).toBeInTheDocument()

    m.interviewAnswer.mockImplementation(async () => {
      turns = [turns[0], { ...turns[1], answer: 'My answer', mode: 'exam', evaluation: evaluation() }]
      return { evaluation: evaluation(), next: null }
    })
    m.getInterviewReport.mockResolvedValue({ answered: 1, pending: 0, failed: 0, skipped: 1, average: 3, verdicts: { good: 0, partial: 1, weak: 0 },
      dimensions: {}, topics: [], turns: [] })
    await userEvent.type(screen.getByLabelText('Your answer'), 'My answer{Enter}')
    expect(await screen.findByText(/That will be all; the interview is over\. Your report is below/)).toBeInTheDocument()
    expect(await screen.findByText(/1 answered · 1 skipped/)).toBeInTheDocument()
    expect(speech.spoken()).toContain('Thank you. That will be all; the interview is over.')
    expect(screen.getByRole('button', { name: /Next question/ })).toBeDisabled()
  })
})

describe('a report whose critiques are still being written', () => {
  const report = (over: Partial<InterviewReport>): InterviewReport => ({ answered: 0, pending: 0, failed: 0, skipped: 0, average: 3,
    verdicts: { good: 0, partial: 1, weak: 0 }, dimensions: {}, topics: [], turns: [], ...over })

  it('shows progress and refreshes until they are all in, surviving a failed refresh', async () => {
    localStorage.setItem('upsc-interview', JSON.stringify({ sessionId: 's1', mode: 'exam', voice: false, filters: { plan: 'topics' } }))
    turns = [{ ...turn(), answer: 'A', mode: 'exam', evaluation: { pending: true } as never }]
    m.getInterviewReport.mockReset()
      .mockResolvedValueOnce(report({ pending: 2 }))
      .mockRejectedValueOnce(new Error('blip'))
      .mockResolvedValueOnce(report({ answered: 1, pending: 1 }))
      .mockResolvedValue(report({ answered: 1, failed: 1 }))
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Report' }))
    expect(await screen.findByText(/finishing your report: 0 of 2 answers reviewed/)).toBeInTheDocument()
    expect(await screen.findByText(/finishing your report: 1 of 2 answers reviewed/, undefined, { timeout: 10_000 })).toBeInTheDocument()
    expect(await screen.findByText(/1 answer couldn't be reviewed/, undefined, { timeout: 5_000 })).toBeInTheDocument()
    expect(screen.getByText(/1 answered/)).toBeInTheDocument()
    expect(m.getInterviewReport).toHaveBeenCalledTimes(4)
  })

  it('stops refreshing when a new interview starts, and words several failures properly', async () => {
    localStorage.setItem('upsc-interview', JSON.stringify({ sessionId: 's1', mode: 'exam', voice: false, filters: { plan: 'topics' } }))
    turns = [{ ...turn(), answer: 'A', mode: 'exam', evaluation: { pending: true } as never }]
    m.getInterviewReport.mockReset().mockResolvedValueOnce(report({ answered: 1, failed: 2 })).mockResolvedValue(report({ pending: 1 }))
    render(<InterviewView stats={stats} onOpen={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Report' }))
    expect(await screen.findByText(/2 answers couldn't be reviewed/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Report' }))
    await screen.findByText(/finishing your report/)
    await userEvent.click(screen.getByRole('button', { name: 'New' }))
    expect(screen.queryByText(/finishing your report/)).toBeNull()
    await new Promise((resolve) => setTimeout(resolve, 3200))
    expect(m.getInterviewReport).toHaveBeenCalledTimes(2)
  })
})
