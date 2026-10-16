import { ClipboardList, ExternalLink, History, Loader2, Play, RotateCcw, Send, SkipForward, SlidersHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  getInterviewReport, getInterviewSession, getInterviewTopics, getSimilarQuestions, interviewAnswer, interviewNext,
} from '../../services/api'
import type { InterviewFilters, InterviewReport, InterviewTopic, SimilarQuestion, Stats, Turn } from '../../types'
import { FeedbackCard, ScoreBars, VerdictPill } from './FeedbackCard'
import { InterviewFiltersPanel } from './InterviewFiltersPanel'

type Mode = 'coach' | 'exam'
const STORE = 'upsc-interview'
const DEFAULT_FILTERS: InterviewFilters = { topics: [], board: '', daf: '', question_mode: 'generated' }

function load(): { sessionId: string | null; mode: Mode; filters: InterviewFilters } {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE) || '{}')
    return { sessionId: raw.sessionId ?? null, mode: raw.mode ?? 'coach', filters: { ...DEFAULT_FILTERS, ...raw.filters } }
  } catch {
    return { sessionId: null, mode: 'coach', filters: DEFAULT_FILTERS }
  }
}

function save(state: { sessionId: string | null; mode: Mode; filters: InterviewFilters }) {
  try { localStorage.setItem(STORE, JSON.stringify(state)) } catch { /* private mode: state just won't persist */ }
}

/** Interview mode: filters on the left, a conversation with the board on the right. */
export function InterviewView({ stats, onOpen }: { stats: Stats | null; onOpen: (id: string, query: string) => void }) {
  const [initial] = useState(load)
  const [topics, setTopics] = useState<InterviewTopic[]>([])
  const [filters, setFilters] = useState<InterviewFilters>(initial.filters)
  const [mode, setMode] = useState<Mode>(initial.mode)
  const [sessionId, setSessionId] = useState<string | null>(initial.sessionId)
  const [turns, setTurns] = useState<Turn[]>([])
  const [busy, setBusy] = useState<'asking' | 'evaluating' | null>(null)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState('')
  const [report, setReport] = useState<InterviewReport | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { getInterviewTopics().then(setTopics).catch(() => setTopics([])) }, [])
  useEffect(() => {
    if (initial.sessionId) getInterviewSession(initial.sessionId).then(setTurns).catch(() => setSessionId(null))
  }, [initial.sessionId])
  useEffect(() => save({ sessionId, mode, filters }), [sessionId, mode, filters])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [turns, busy, report])

  const open = [...turns].reverse().find((t) => t.answer === null && !t.evaluation?.skipped)

  const run = async (kind: 'asking' | 'evaluating', action: () => Promise<string>) => {
    setBusy(kind); setError(''); setReport(null)
    try {
      const sid = await action()
      setTurns(await getInterviewSession(sid))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const nextQuestion = () => run('asking', async () => {
    const r = await interviewNext(sessionId, filters)
    setSessionId(r.session_id)
    return r.session_id
  })

  const send = () => {
    const text = draft.trim()
    if (!text || !sessionId || !open || busy) return
    run('evaluating', async () => {
      await interviewAnswer(sessionId, text, mode, filters)
      setDraft('')
      return sessionId
    })
  }

  const newConversation = () => { setSessionId(null); setTurns([]); setReport(null); setError(''); setDraft('') }
  const showReport = async () => { if (sessionId) setReport(await getInterviewReport(sessionId)) }

  return (
    <div className="grid gap-6 md:grid-cols-[280px_1fr]">
      <aside className={`${showFilters ? 'block' : 'hidden'} md:block md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:self-start md:overflow-y-auto md:pr-2`}>
        <InterviewFiltersPanel topics={topics} stats={stats} filters={filters} onChange={setFilters} />
      </aside>

      <section className="flex min-h-[70vh] min-w-0 flex-col rounded-xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-4 py-2.5 dark:border-stone-800">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowFilters(!showFilters)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-xs md:hidden dark:border-stone-700">
              <SlidersHorizontal size={13} /> Filters{filters.topics.length ? ` (${filters.topics.length})` : ''}
            </button>
            <span className="text-sm font-medium">Interview board</span>
            {filters.topics.length > 0 && <span className="hidden text-xs text-stone-400 sm:inline">{filters.topics.join(' · ')}</span>}
          </div>
          <div className="flex items-center gap-1">
            <HeaderButton onClick={showReport} disabled={!turns.some((t) => t.answer)} icon={<ClipboardList size={14} />} label="Report" />
            <HeaderButton onClick={newConversation} disabled={!turns.length} icon={<RotateCcw size={14} />} label="New" />
          </div>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
          {!turns.length && !busy && (
            <div className="mx-auto max-w-md py-12 text-center text-sm text-stone-500">
              <p className="mb-1 font-medium text-stone-700 dark:text-stone-300">Practise with the board</p>
              <p className="mb-5">Pick one or more topics on the left, then start. Good answers earn up to two follow-ups; weak ones get critique and a new question.</p>
              <button onClick={nextQuestion} disabled={!filters.topics.length}
                className="inline-flex items-center gap-2 rounded-md bg-sandstone-600 px-4 py-2 text-sm font-medium text-white hover:bg-sandstone-700 disabled:opacity-40">
                <Play size={14} /> Start
              </button>
            </div>
          )}

          {turns.map((t, i) => {
            const next = turns[i + 1]
            const followUpNext = Boolean(next && next.main_index === t.main_index && next.depth === t.depth + 1)
            const ev = t.evaluation
            return (
              <div key={t.id} className="space-y-3">
                {t.depth === 0 && t.main_index > 1 && <hr className="border-stone-100 dark:border-stone-800" />}
                <BoardBubble t={t} onOpen={onOpen} coach={mode === 'coach'} />
                {ev?.skipped && <p className="pl-10 text-xs text-stone-400">Skipped</p>}
                {t.answer && <CandidateBubble text={t.answer} />}
                {t.answer && ev && !ev.skipped && (
                  t.mode === 'coach'
                    ? <div className="pl-10"><FeedbackCard e={ev} followUpNext={followUpNext} /></div>
                    : <p className="pl-10 text-xs text-stone-400">Exam mode: feedback saved for the report.</p>
                )}
              </div>
            )
          })}

          {busy && (
            <p className="flex items-center gap-2 pl-10 text-sm text-stone-500">
              <Loader2 size={15} className="animate-spin" />
              {busy === 'asking' ? 'The board is preparing a question…' : 'The board is evaluating your answer…'}
            </p>
          )}
          {error && <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">{error}</p>}
          {report && <ReportCard r={report} />}
          <div ref={bottom} />
        </div>

        <footer className="space-y-2 border-t border-stone-200 p-3 dark:border-stone-800">
          <div className="flex items-center justify-between gap-2">
            <ModeToggle mode={mode} onChange={setMode} />
            <button onClick={nextQuestion} disabled={busy !== null || !filters.topics.length}
              className="inline-flex items-center gap-1 text-xs text-stone-500 hover:text-sandstone-600 disabled:opacity-40">
              <SkipForward size={13} /> {turns.length ? 'Next question' : 'Start'}
            </button>
          </div>
          <div className="flex gap-2">
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} disabled={!open || busy !== null}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder={open ? 'Answer as you would in the room… (Enter to send, Shift+Enter for a new line)' : 'Start or ask for the next question first'}
              className="flex-1 resize-none rounded-lg border border-stone-300 bg-white p-2.5 text-[15px] focus:border-sandstone-500 focus:ring-2 focus:ring-sandstone-500/20 focus:outline-none disabled:bg-stone-50 dark:border-stone-700 dark:bg-stone-950 dark:disabled:bg-stone-900" />
            <button onClick={send} disabled={!open || !draft.trim() || busy !== null} aria-label="Send answer"
              className="self-end rounded-lg bg-sandstone-600 p-2.5 text-white hover:bg-sandstone-700 disabled:opacity-40">
              <Send size={16} />
            </button>
          </div>
        </footer>
      </section>
    </div>
  )
}

function HeaderButton({ onClick, disabled, icon, label }: { onClick: () => void; disabled: boolean; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-stone-600 hover:bg-stone-100 disabled:opacity-40 dark:text-stone-400 dark:hover:bg-stone-800">
      {icon}{label}
    </button>
  )
}

function ModeToggle({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div role="radiogroup" aria-label="Feedback mode" className="flex rounded-full bg-stone-100 p-0.5 dark:bg-stone-800">
        {(['coach', 'exam'] as const).map((m) => (
          <button key={m} role="radio" aria-checked={mode === m} onClick={() => onChange(m)}
            className={`rounded-full px-3 py-1 font-medium transition ${mode === m
              ? 'bg-white text-stone-900 shadow-sm dark:bg-stone-950 dark:text-white' : 'text-stone-500'}`}>
            {m === 'coach' ? 'Coach Mode' : 'Exam Mode'}
          </button>
        ))}
      </div>
      <span className="hidden text-stone-400 sm:inline">{mode === 'coach' ? 'Feedback after every answer' : 'Feedback only in the report'}</span>
    </div>
  )
}

function SourceLine({ t, onOpen }: { t: Turn; onOpen: (id: string, query: string) => void }) {
  const s = t.source
  const cls = 'text-xs text-stone-400'
  if (s.type === 'followup') return <span className={cls}>Follow-up {t.depth} of 2</span>
  if (s.type === 'generated') {
    const label = `New question · ${s.angle === 'news' ? 'from the news' : s.angle === 'daf' ? 'from your DAF' : 'on the topic'}${s.based_on ? `: ${s.based_on}` : ''}`
    return s.url ? (
      <a href={s.url} target="_blank" rel="noreferrer" className={`${cls} inline-flex items-center gap-1 hover:text-sandstone-600`}>
        {label} · {s.publisher} <ExternalLink size={11} />
      </a>
    ) : <span className={cls}>{label}</span>
  }
  if (s.type === 'daf') return <span className={cls}>From your DAF{s.daf_item ? `: ${s.daf_item}` : ''}</span>
  if (s.type === 'current') {
    return (
      <a href={s.url} target="_blank" rel="noreferrer" className={`${cls} inline-flex items-center gap-1 hover:text-sandstone-600`}>
        From the news: {s.title} · {s.publisher} <ExternalLink size={11} />
      </a>
    )
  }
  return (
    <button onClick={() => s.transcript_id && onOpen(s.transcript_id, '')} className={`${cls} hover:text-sandstone-600`}>
      Asked in CSE {s.cse_year} · {s.board} board · view transcript
    </button>
  )
}

function BoardBubble({ t, onOpen, coach }: { t: Turn; onOpen: (id: string, query: string) => void; coach: boolean }) {
  const [similar, setSimilar] = useState<SimilarQuestion[] | null>(null)
  const [open, setOpen] = useState(false)
  const toggle = async () => {
    setOpen(!open)
    if (!similar) setSimilar(await getSimilarQuestions(t.id).catch(() => []))
  }
  return (
    <div className="flex gap-2.5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sandstone-100 text-xs font-semibold text-sandstone-700 dark:bg-sandstone-500/20 dark:text-sandstone-300">
        {t.depth ? 'F' : 'Q'}
      </div>
      <div className="min-w-0 space-y-1">
        <div className="text-xs font-medium text-sandstone-700 dark:text-sandstone-300">{t.topic}</div>
        <p className="text-[15px] leading-relaxed text-stone-900 dark:text-stone-100">{t.question}</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <SourceLine t={t} onOpen={onOpen} />
          {coach && (
            <button onClick={toggle} className="inline-flex items-center gap-1 text-xs text-sandstone-600 hover:underline dark:text-sandstone-400">
              <History size={12} /> {open ? 'Hide' : 'How have boards asked this?'}
            </button>
          )}
        </div>
        {coach && open && <SimilarMoments items={similar} onOpen={onOpen} />}
      </div>
    </div>
  )
}

/** Coach-mode helper: the real past questions closest to this one, and what the board asked next. */
function SimilarMoments({ items, onOpen }: { items: SimilarQuestion[] | null; onOpen: (id: string, query: string) => void }) {
  if (!items) return <p className="flex items-center gap-1.5 text-xs text-stone-400"><Loader2 size={12} className="animate-spin" /> Looking through past interviews…</p>
  if (!items.length) return <p className="text-xs text-stone-400">No similar questions found.</p>
  return (
    <ul className="mt-1 space-y-2 border-l-2 border-sandstone-100 pl-3 dark:border-sandstone-900">
      {items.map((q) => (
        <li key={q.id} className="text-sm">
          <p className="text-stone-800 dark:text-stone-200">{q.text}</p>
          {q.follow_up && <p className="text-stone-500 dark:text-stone-400"><span className="text-xs uppercase">then </span>{q.follow_up}</p>}
          <button onClick={() => onOpen(q.transcript_id, '')} className="text-xs text-stone-400 hover:text-sandstone-600">
            {q.member} · {q.board} board · CSE {q.cse_year} · open transcript
          </button>
        </li>
      ))}
    </ul>
  )
}

function CandidateBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-tr-sm bg-sandstone-600 px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap text-white">{text}</p>
    </div>
  )
}

function ReportCard({ r }: { r: InterviewReport }) {
  if (!r.answered) return <p className="text-sm text-stone-500">Answer a few questions first to see a report.</p>
  return (
    <section className="space-y-4 rounded-xl border border-sandstone-200 bg-sandstone-50/50 p-5 dark:border-sandstone-900 dark:bg-sandstone-500/5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-lg tracking-wide">Report</h3>
        <span className="text-sm text-stone-500">
          {r.answered} answered · {r.skipped} skipped · average {r.average.toFixed(1)}/5 ·{' '}
          {r.verdicts.good} good, {r.verdicts.partial} partial, {r.verdicts.weak} weak
        </span>
      </div>
      <ScoreBars scores={r.dimensions} />
      <div className="flex flex-wrap gap-2">
        {r.topics.map((t) => (
          <span key={t.topic} className="rounded-md bg-white px-2 py-1 text-xs shadow-sm dark:bg-stone-900">
            {t.topic}: <b>{t.average.toFixed(1)}</b> ({t.answered})
          </span>
        ))}
      </div>
      <ol className="space-y-3">
        {r.turns.map((t) => (
          <li key={t.id} className="rounded-lg bg-white p-3 text-sm shadow-sm dark:bg-stone-900">
            <div className="mb-1 flex items-start justify-between gap-2">
              <p className="font-medium">{t.depth ? `Follow-up: ` : ''}{t.question}</p>
              {t.evaluation && <VerdictPill verdict={t.evaluation.verdict} average={t.evaluation.average} />}
            </div>
            <p className="mb-1 text-stone-500 italic">“{t.answer}”</p>
            {t.evaluation && <p className="text-stone-700 dark:text-stone-300">{t.evaluation.critique}</p>}
          </li>
        ))}
      </ol>
    </section>
  )
}
