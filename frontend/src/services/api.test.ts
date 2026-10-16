import { beforeEach, describe, expect, it, vi } from 'vitest'
import { emptyFilters } from '../types'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => {
  const isAxiosError = (e: unknown) => Boolean((e as { isAxiosError?: boolean })?.isAxiosError)
  return { default: { create: () => http, isAxiosError } }
})

const api = await import('./api')

beforeEach(() => {
  http.get.mockReset().mockResolvedValue({ data: 'ok' })
  http.post.mockReset().mockResolvedValue({ data: 'posted' })
})

describe('REST calls', () => {
  it('sends only the filters that are set', async () => {
    const f = { ...emptyFilters(), board: 'BB Swain', cse_year: '2025', topics: ['Economy'], has_marks: true }
    await api.searchTranscripts('gdp', f, 24, 24, 'marks')
    expect(http.get).toHaveBeenCalledWith('/api/search', { params: {
      q: 'gdp', limit: 24, offset: 24, sort: 'marks', board: 'BB Swain', cse_year: 2025, exam: undefined,
      background: undefined, optional_tag: undefined, state: undefined, interest: undefined, topic: ['Economy'],
      has_marks: true } })
    await api.getFacets(emptyFilters())
    expect(http.get.mock.calls[1][1].params.q).toBeUndefined()
  })

  it('wraps each endpoint', async () => {
    await api.getStats()
    await api.getTranscript('u 1')
    await api.getInterviewTopics()
    await api.getInterviewSession('s1')
    await api.getInterviewReport('s1')
    await api.getSimilarQuestions(7)
    expect(http.get.mock.calls.map((c) => c[0])).toEqual([
      '/api/stats', '/api/transcripts/u%201', '/api/interview/topics', '/api/interview/sessions/s1',
      '/api/interview/sessions/s1/report', '/api/interview/turns/7/similar'])
  })

  it('posts interview requests with cleaned filters', async () => {
    const f = { topics: ['Economy'], board: '', daf: '  ', question_mode: 'real' as const }
    expect(await api.interviewNext(null, f)).toBe('posted')
    await api.interviewAnswer('s1', 'An answer', 'exam', f)
    expect(http.post.mock.calls[0]).toEqual(['/api/interview/next', { session_id: null,
      filters: { topics: ['Economy'], board: null, daf: null, question_mode: 'real' } }])
    expect(http.post.mock.calls[1][1]).toMatchObject({ session_id: 's1', answer: 'An answer', mode: 'exam' })
  })

  it('turns API errors into readable messages', async () => {
    http.post.mockRejectedValueOnce({ isAxiosError: true, response: { data: { detail: 'Pick at least one topic' } } })
    await expect(api.interviewNext(null, { topics: [], board: '', daf: '', question_mode: 'generated' }))
      .rejects.toThrow('Pick at least one topic')
    http.post.mockRejectedValueOnce({ isAxiosError: true, message: 'Network Error', response: { data: { detail: [{ msg: 'bad' }] } } })
    await expect(api.interviewAnswer('s', 'a', 'coach', { topics: [], board: '', daf: '', question_mode: 'real' }))
      .rejects.toThrow('[{"msg":"bad"}]')
    http.post.mockRejectedValueOnce('boom')
    await expect(api.interviewNext(null, { topics: [], board: '', daf: '', question_mode: 'real' })).rejects.toThrow('boom')
  })
})

function streamOf(chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      for (const ch of chunks) c.enqueue(new TextEncoder().encode(ch))
      c.close()
    },
  })
  return new Response(body, { status: 200 })
}

const handlers = () => ({ onSources: vi.fn(), onDelta: vi.fn(), onError: vi.fn(), onDone: vi.fn() })

describe('ask (server-sent events)', () => {
  it('parses events split across chunks', async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamOf([
      'event: sources\ndata: [{"id": "u1"}]\n\nevent: del', 'ta\ndata: "Hel"\n\n', 'event: delta\ndata: "lo"\n\n',
      ': keep-alive\n\n', 'event: done\ndata: {}\n\n']))
    vi.stubGlobal('fetch', fetchMock)
    const h = handlers()
    await api.ask('Q?', { ...emptyFilters(), topics: ['Economy'] }, 'kw', h, new AbortController().signal)
    expect(h.onSources).toHaveBeenCalledWith([{ id: 'u1' }])
    expect(h.onDelta.mock.calls.map((c) => c[0]).join('')).toBe('Hello')
    expect(h.onDone).toHaveBeenCalledTimes(1)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ question: 'Q?', q: 'kw', filters: { topics: ['Economy'] } })
  })

  it('reports error events and failed requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamOf(['event: error\ndata: "No transcripts matched."\n\n'])))
    let h = handlers()
    await api.ask('Q?', emptyFilters(), '', h, new AbortController().signal)
    expect(h.onError).toHaveBeenCalledWith('No transcripts matched.')
    expect(h.onDone).not.toHaveBeenCalled()

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('nope', { status: 500 })))
    h = handlers()
    await api.ask('Q?', emptyFilters(), '', h, new AbortController().signal)
    expect(h.onError).toHaveBeenCalledWith('Request failed (500)')
  })

  it('finishes when the stream ends without a done event', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(streamOf(['event: delta\ndata: "x"\n\n'])))
    const h = handlers()
    await api.ask('Q?', emptyFilters(), '', h, new AbortController().signal)
    expect(h.onDone).toHaveBeenCalledTimes(1)
  })
})
