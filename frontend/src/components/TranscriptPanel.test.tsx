import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import * as api from '../services/api'
import { transcript } from '../test/fixtures'
import { TranscriptPanel } from './TranscriptPanel'

vi.mock('../services/api', () => ({ getTranscript: vi.fn() }))
const getTranscript = vi.mocked(api.getTranscript)

beforeEach(() => { getTranscript.mockReset() })

it('shows the formatted outline, the original text, and closes on Escape', async () => {
  getTranscript.mockResolvedValue(transcript())
  const onClose = vi.fn()
  const { container } = render(<TranscriptPanel id="u1" query="dharma" onClose={onClose} />)
  expect(await screen.findByText('Why do you read the Gita?')).toBeInTheDocument()
  expect(screen.getByText('Chairperson')).toBeInTheDocument()
  expect(screen.getByText('lady member')).toBeInTheDocument()
  expect(screen.getByText('Forenoon session')).toBeInTheDocument()
  expect(screen.getByText('Went well overall')).toBeInTheDocument()
  expect(screen.getByText(/DAF/)).toBeInTheDocument()                  // no DAF line in the header facts
  expect(container.querySelector('mark')).toHaveTextContent('dharma')
  expect(screen.getByText('2 Telegram messages joined', { exact: false })).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: 'Original text' }))
  expect(container.querySelector('pre')).toHaveTextContent('Chairman Why do you read the Gita?')
  await userEvent.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalled()
})

it('falls back to the original text without an outline', async () => {
  getTranscript.mockResolvedValue(transcript({ structure: null, message_ids: [11], alias: null }))
  const { container } = render(<TranscriptPanel id="u1" query="" onClose={() => {}} />)
  expect(await screen.findByText('single Telegram message', { exact: false })).toBeInTheDocument()
  expect(container.querySelector('pre')).not.toBeNull()
  expect(screen.getByText('Anonymous candidate')).toBeInTheDocument()
})

it('reports a load failure', async () => {
  getTranscript.mockRejectedValue(new Error('404'))
  render(<TranscriptPanel id="nope" query="" onClose={() => {}} />)
  expect(await screen.findByText('Could not load this transcript.')).toBeInTheDocument()
})
