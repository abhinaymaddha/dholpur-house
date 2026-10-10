import { Loader2, Send, Sparkles, Square, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Answer } from '../lib/text'
import { ask } from '../services/api'
import type { Filters, Source, Stats } from '../types'
import { MetaLine } from './MetaLine'

const EXAMPLES = [
  'How does this board usually open the interview?',
  'What do boards ask candidates who switched from engineering?',
  'Which situational questions about being a DM come up?',
  'What was asked about India–Bangladesh relations?',
]

/** "Ask AI" inside Browse: answers from the transcripts matching the current search and filters. */
export function AskPanel({ filters, q, scope, stats, onOpen, onClose }: {
  filters: Filters
  q: string
  scope: string
  stats: Stats | null
  onOpen: (id: string, query: string) => void
  onClose: () => void
}) {
  const [question, setQuestion] = useState('')
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
      await ask(text, filters, q, {
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
    <section className="space-y-3 rounded-xl border border-indigo-200 bg-indigo-50/40 p-4 dark:border-indigo-900 dark:bg-indigo-500/5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold text-indigo-800 dark:text-indigo-300"><Sparkles size={15} /> Ask AI</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">Answers from {scope}. Narrow the search or filters to focus it.</p>
        </div>
        <button aria-label="Close Ask AI" onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-600 dark:hover:bg-slate-800"><X size={16} /></button>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); submit() }} className="flex gap-2">
        <textarea autoFocus value={question} onChange={(e) => setQuestion(e.target.value)} rows={2}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          placeholder="e.g. What do these boards ask doctors about rural postings?"
          className="flex-1 resize-none rounded-lg border border-slate-300 bg-white p-2.5 text-[15px] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none dark:border-slate-700 dark:bg-slate-900" />
        {busy ? (
          <button type="button" onClick={() => abortRef.current?.abort()} aria-label="Stop" className="self-end rounded-lg bg-slate-200 p-2.5 dark:bg-slate-800"><Square size={16} /></button>
        ) : (
          <button type="submit" disabled={question.trim().length < 3} aria-label="Ask" className="self-end rounded-lg bg-indigo-600 p-2.5 text-white hover:bg-indigo-700 disabled:opacity-40"><Send size={16} /></button>
        )}
      </form>

      {!answer && !busy && !error && sources.length === 0 && (
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((ex) => (
            <button key={ex} onClick={() => submit(ex)} className="rounded-full border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-indigo-400 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">{ex}</button>
          ))}
        </div>
      )}

      {(busy || answer || error) && (
        <div className="rounded-lg bg-white p-4 text-[15px] dark:bg-slate-900">
          {phase === 'retrieving' && <Status text="Finding relevant transcripts…" />}
          {phase === 'answering' && !answer && <Status text={`Reading ${sources.length} transcripts… (${stats?.llm_model ?? 'AI'})`} />}
          {answer && <Answer text={answer} onCite={cite} />}
          {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        </div>
      )}

      {sources.length > 0 && (
        <ol className="grid gap-2 sm:grid-cols-2">
          {sources.map((s, i) => (
            <li key={s.id} ref={(el) => { sourceRefs.current[i] = el }}>
              <button onClick={() => onOpen(s.id, question)} className="h-full w-full rounded-lg border border-slate-200 bg-white p-3 text-left hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900">
                <div className="mb-1 flex items-center gap-2">
                  <span className="rounded bg-indigo-100 px-1.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">S{i + 1}</span>
                  <span className="truncate text-sm font-medium">{s.alias || 'Anonymous candidate'}</span>
                </div>
                <MetaLine t={s} />
                <p className="mt-1.5 line-clamp-2 text-xs text-slate-600 dark:text-slate-400">{s.excerpts[0]?.text}</p>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function Status({ text }: { text: string }) {
  return <p className="flex items-center gap-2 text-sm text-slate-500"><Loader2 size={16} className="animate-spin" /> {text}</p>
}
