import { Loader2, Send, Square } from 'lucide-react'
import { useRef, useState } from 'react'
import { Answer } from '../lib/text'
import { ask } from '../services/api'
import type { Filters, Source, Stats } from '../types'
import { FiltersBar } from './FiltersBar'
import { MetaLine } from './MetaLine'

const EXAMPLES = [
  'What do boards ask candidates with an engineering background who switched to civil services?',
  'Which questions were asked about India–Bangladesh relations?',
  'How does Lt Gen Raj Shukla’s board usually open the interview?',
  'What situational questions were asked about being a District Magistrate?',
]

export function AskView({ stats, onOpen }: { stats: Stats | null; onOpen: (id: string, query: string) => void }) {
  const [question, setQuestion] = useState('')
  const [filters, setFilters] = useState<Filters>({ board: '', cse_year: '', exam: '' })
  const [sources, setSources] = useState<Source[]>([])
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState('')
  const [phase, setPhase] = useState<'idle' | 'retrieving' | 'answering'>('idle')
  const abortRef = useRef<AbortController | null>(null)
  const sourceRefs = useRef<(HTMLLIElement | null)[]>([])

  const submit = async (text = question) => {
    if (text.trim().length < 3 || phase !== 'idle') return
    setQuestion(text)
    setSources([]); setAnswer(''); setError('')
    setPhase('retrieving')
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await ask(text, filters, {
        onSources: (s) => { setSources(s); setPhase('answering') },
        onDelta: (d) => setAnswer((a) => a + d),
        onError: setError,
        onDone: () => {},
      }, controller.signal)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError('Something went wrong while answering.')
    } finally {
      setPhase('idle')
    }
  }

  const cite = (n: number) => sourceRefs.current[n - 1]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  const busy = phase !== 'idle'

  return (
    <div className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); submit() }} className="space-y-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          rows={3}
          placeholder="Ask about the transcripts, e.g. What do boards ask doctors about rural postings?"
          className="w-full resize-none rounded-lg border border-slate-300 bg-white p-3 text-[15px] shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none dark:border-slate-700 dark:bg-slate-900"
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <FiltersBar stats={stats} filters={filters} onChange={setFilters} />
          {busy ? (
            <button type="button" onClick={() => abortRef.current?.abort()} className="inline-flex h-9 items-center gap-2 rounded-md bg-slate-200 px-4 text-sm font-medium dark:bg-slate-800">
              <Square size={14} /> Stop
            </button>
          ) : (
            <button type="submit" disabled={question.trim().length < 3} className="inline-flex h-9 items-center gap-2 rounded-md bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">
              <Send size={14} /> Ask
            </button>
          )}
        </div>
      </form>

      {!answer && !busy && !error && sources.length === 0 && (
        <div className="space-y-2">
          <p className="text-sm text-slate-500">Try one of these:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => submit(ex)} className="rounded-full border border-slate-300 px-3 py-1.5 text-left text-sm text-slate-700 hover:border-indigo-400 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300">
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {(busy || answer || error) && (
        <section className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          {phase === 'retrieving' && <Status text="Finding relevant transcripts…" />}
          {phase === 'answering' && !answer && <Status text={`Reading ${sources.length} transcripts… (${stats?.llm_model ?? 'LLM'})`} />}
          {answer && <Answer text={answer} onCite={cite} />}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </section>
      )}

      {sources.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-slate-600 dark:text-slate-300">Sources</h3>
          <ol className="space-y-2">
            {sources.map((s, i) => (
              <li key={s.id} ref={(el) => { sourceRefs.current[i] = el }}>
                <button onClick={() => onOpen(s.id, question)} className="w-full rounded-lg border border-slate-200 bg-white p-3 text-left hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="rounded bg-indigo-100 px-1.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">S{i + 1}</span>
                    <span className="truncate text-sm font-medium">{s.alias || 'Anonymous candidate'}</span>
                  </div>
                  <MetaLine t={s} />
                  <p className="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-400">{s.excerpts[0]?.text}</p>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}

function Status({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 text-sm text-slate-500">
      <Loader2 size={16} className="animate-spin" /> {text}
    </p>
  )
}
