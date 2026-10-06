import axios from 'axios'
import type { Facets, Filters, SearchResponse, SortOrder, Source, Stats, Transcript } from '../types'

const baseURL = import.meta.env.VITE_API_URL ?? ''
// FastAPI reads repeated keys (topic=a&topic=b), not topic[]=a
const http = axios.create({ baseURL, paramsSerializer: { indexes: null } })

function filterParams(f: Filters) {
  return {
    board: f.board || undefined,
    cse_year: f.cse_year ? Number(f.cse_year) : undefined,
    exam: f.exam || undefined,
    background: f.background || undefined,
    optional_tag: f.optional_tag || undefined,
    state: f.state || undefined,
    interest: f.interest || undefined,
    topic: f.topics.length ? f.topics : undefined,
    has_marks: f.has_marks || undefined,
  }
}

function filterBody(f: Filters) {
  const { topic, ...rest } = filterParams(f)
  return { ...rest, topics: topic ?? [] }
}

export async function getStats(): Promise<Stats> {
  return (await http.get<Stats>('/api/stats')).data
}

export async function searchTranscripts(
  q: string, filters: Filters, offset = 0, limit = 20, sort: SortOrder = 'recent',
): Promise<SearchResponse> {
  const params = { q, limit, offset, sort, ...filterParams(filters) }
  return (await http.get<SearchResponse>('/api/search', { params })).data
}

export async function getFacets(filters: Filters): Promise<Facets> {
  return (await http.get<Facets>('/api/facets', { params: filterParams(filters) })).data
}

export async function getTranscript(id: string): Promise<Transcript> {
  return (await http.get<Transcript>(`/api/transcripts/${encodeURIComponent(id)}`)).data
}

export interface AskHandlers {
  onSources: (sources: Source[]) => void
  onDelta: (text: string) => void
  onError: (message: string) => void
  onDone: () => void
}

/** POST /api/ask and consume its server-sent events (fetch, since EventSource can't POST). */
export async function ask(question: string, filters: Filters, handlers: AskHandlers, signal: AbortSignal) {
  const res = await fetch(`${baseURL}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, filters: filterBody(filters) }),
    signal,
  })
  if (!res.ok || !res.body) {
    handlers.onError(`Request failed (${res.status})`)
    return
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let finished = false
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const event = /^event: (.*)$/m.exec(raw)?.[1]
      const data = /^data: (.*)$/m.exec(raw)?.[1]
      if (!event || data === undefined) continue
      const payload = JSON.parse(data)
      if (event === 'sources') handlers.onSources(payload)
      else if (event === 'delta') handlers.onDelta(payload)
      else if (event === 'error') { handlers.onError(payload); finished = true }
      else if (event === 'done') { handlers.onDone(); finished = true }
    }
  }
  if (!finished) handlers.onDone()
}
