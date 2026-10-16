import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import * as api from '../services/api'
import { source, stats } from '../test/fixtures'
import { emptyFilters } from '../types'
import { AskPanel } from './AskPanel'

vi.mock('../services/api', () => ({ ask: vi.fn() }))
const ask = vi.mocked(api.ask)

beforeEach(() => { ask.mockReset() })

const panel = (onOpen = vi.fn(), onClose = vi.fn()) =>
  render(<AskPanel filters={emptyFilters()} q="" scope="all 4 transcripts" stats={stats} onOpen={onOpen} onClose={onClose} />)

it('streams an answer with sources and opens a cited transcript', async () => {
  ask.mockImplementation(async (_q, _f, _kw, h) => {
    h.onSources([source(), source({ id: 'u2', alias: null })])
    h.onDelta('Boards ask about the Gita ')
    h.onDelta('[S1].')
    h.onDone()
  })
  const onOpen = vi.fn()
  panel(onOpen)
  expect(screen.getByText(/Answers from all 4 transcripts/)).toBeInTheDocument()
  await userEvent.type(screen.getByRole('textbox'), 'What about the Gita?{Enter}')
  expect(await screen.findByText(/Boards ask about the Gita/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'S1' }))
  await userEvent.click(screen.getByRole('button', { name: /Anonymous candidate/ }))
  expect(onOpen).toHaveBeenCalledWith('u2', 'What about the Gita?')
})

it('asks an example question and shows errors', async () => {
  ask.mockImplementation(async (_q, _f, _kw, h) => { h.onError('No transcripts matched.') })
  panel()
  await userEvent.click(screen.getByRole('button', { name: /How does this board usually open/ }))
  expect(await screen.findByText('No transcripts matched.')).toBeInTheDocument()
  expect(ask.mock.calls[0][0]).toBe('How does this board usually open the interview?')
})

it('shows progress, can be stopped, and ignores aborts', async () => {
  let release: () => void = () => {}
  ask.mockImplementation((_q, _f, _kw, h, signal) => new Promise<void>((resolve, reject) => {
    h.onSources([source()])
    release = resolve
    signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })))
  }))
  panel()
  await userEvent.type(screen.getByRole('textbox'), 'Long question?')
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
  expect(await screen.findByText(/Reading 1 transcripts… \(test-model\)/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Stop' }))
  expect(await screen.findByRole('button', { name: 'Ask' })).toBeInTheDocument()
  expect(screen.queryByText('Something went wrong while answering.')).toBeNull()
  release()
})

it('reports unexpected failures and closes', async () => {
  ask.mockRejectedValue(new Error('network'))
  const onClose = vi.fn()
  panel(vi.fn(), onClose)
  await userEvent.type(screen.getByRole('textbox'), 'Why?{Enter}')
  expect(await screen.findByText('Something went wrong while answering.')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Close Ask AI' }))
  expect(onClose).toHaveBeenCalled()
})

it('does not ask very short questions', async () => {
  panel()
  await userEvent.type(screen.getByRole('textbox'), 'hi{Enter}')
  expect(ask).not.toHaveBeenCalled()
})
