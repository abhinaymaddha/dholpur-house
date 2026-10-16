import { ExternalLink, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { highlightTerms } from '../lib/format'
import { getTranscript } from '../services/api'
import type { Outline, OutlineSection, Transcript } from '../types'
import { MetaLine } from './MetaLine'
import { TagChips } from './TranscriptCard'

/** Slide-over reader for one transcript: formatted outline, or the original text. */
export function TranscriptPanel({ id, query, onClose }: { id: string; query: string; onClose: () => void }) {
  const [t, setT] = useState<Transcript | null>(null)
  const [error, setError] = useState('')
  const [view, setView] = useState<'formatted' | 'original'>('formatted')

  // App remounts the panel per transcript (key={id}), so state starts empty for each one.
  useEffect(() => {
    getTranscript(id).then(setT).catch(() => setError('Could not load this transcript.'))
  }, [id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const formatted = view === 'formatted' && t?.structure && t.structure.sections.length > 0

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-stone-900/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-3xl flex-col bg-white shadow-xl dark:bg-stone-950">
        <header className="space-y-2 border-b border-stone-200 p-4 dark:border-stone-800">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <h2 className="truncate text-xl">{t?.alias || 'Anonymous candidate'}</h2>
              {t && <MetaLine t={t} />}
            </div>
            <button aria-label="Close" onClick={onClose} className="rounded p-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800">
              <X size={20} />
            </button>
          </div>
          {t && <TagChips t={t} max={8} />}
          {t && (
            <div className="flex gap-1 pt-1">
              {(['formatted', 'original'] as const).map((v) => (
                <button key={v} onClick={() => setView(v)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${view === v
                    ? 'bg-sandstone-600 text-stone-50'
                    : 'text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800'}`}>
                  {v === 'formatted' ? 'Formatted' : 'Original text'}
                </button>
              ))}
            </div>
          )}
        </header>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {error && <p className="text-red-600">{error}</p>}
          {!t && !error && <Loader2 className="animate-spin text-stone-400" />}
          {t && formatted && <FormattedTranscript outline={t.structure!} daf={t.daf} query={query} />}
          {t && !formatted && (
            <pre className="font-serif text-[15px] leading-relaxed whitespace-pre-wrap text-stone-800 dark:text-stone-200">
              {highlightTerms(t.text, query)}
            </pre>
          )}
        </div>

        {t && (
          <footer className="flex items-center justify-between border-t border-stone-200 p-3 text-xs text-stone-500 dark:border-stone-800">
            <span>{t.question_count} questions · {t.message_ids.length > 1 ? `${t.message_ids.length} Telegram messages joined` : 'single Telegram message'}</span>
            <a href={t.telegram_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sandstone-600 hover:underline dark:text-sandstone-400">
              Original post <ExternalLink size={12} />
            </a>
          </footer>
        )}
      </aside>
    </div>
  )
}

function FormattedTranscript({ outline, daf, query }: { outline: Outline; daf: string | null; query: string }) {
  const facts = outline.header.filter((h): h is { key: string; value: string } => 'key' in h)
  const lines = outline.header.filter((h): h is { text: string } => 'text' in h)
  return (
    <article className="space-y-6 font-serif">
      {(facts.length > 0 || lines.length > 0) && (
        <div className="rounded-lg bg-stone-50 p-4 text-sm dark:bg-stone-900">
          {facts.length > 0 && (
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
              {facts.map((f, i) => (
                <div key={i} className="contents">
                  <dt className="font-medium text-stone-500 dark:text-stone-400">{f.key}</dt>
                  <dd className="text-stone-800 dark:text-stone-200">{highlightTerms(f.value, query)}</dd>
                </div>
              ))}
            </dl>
          )}
          {lines.map((l, i) => <p key={i} className="mt-1 text-stone-700 dark:text-stone-300">{highlightTerms(l.text, query)}</p>)}
          {daf && facts.every((f) => !/daf|keyword/i.test(f.key)) && (
            <p className="mt-2"><span className="font-medium text-stone-500">DAF </span>{daf}</p>
          )}
        </div>
      )}
      {outline.sections.map((s, i) => <Section key={i} s={s} query={query} />)}
    </article>
  )
}

function Section({ s, query }: { s: OutlineSection; query: string }) {
  const isMember = Boolean(s.member)
  const isNote = (it: OutlineSection['items'][number]) => it.kind === 'note' || (!isMember && s.title !== 'Questions')
  // Question numbers, counting only the items shown as questions
  const numbers = s.items.reduce<number[]>((acc, it) => [...acc, (acc.at(-1) ?? 0) + (isNote(it) ? 0 : 1)], [])
  return (
    <section>
      <h3 className={`mb-2 flex items-baseline gap-2 border-b pb-1 ${isMember ? 'border-sandstone-100 dark:border-sandstone-900' : 'border-stone-100 dark:border-stone-800'}`}>
        <span className={`font-display text-base tracking-wide ${isMember ? 'text-sandstone-700 dark:text-sandstone-300' : 'text-stone-600 dark:text-stone-300'}`}>
          {s.member ?? s.title}
        </span>
        {s.member && s.gender === 'female' && <span className="text-xs text-stone-400">lady member</span>}
        {s.member && s.title.toLowerCase() !== s.member.toLowerCase() && (
          <span className="truncate text-xs text-stone-400">{s.title}</span>
        )}
      </h3>
      <ol className="space-y-1.5">
        {s.items.map((it, i) => {
          if (isNote(it)) {
            return (
              <li key={i} className={`text-[14px] leading-relaxed ${isMember ? 'border-l-2 border-stone-200 pl-3 text-stone-500 italic dark:border-stone-700 dark:text-stone-400' : 'text-stone-700 dark:text-stone-300'}`}>
                {highlightTerms(it.text, query)}
              </li>
            )
          }
          return (
            <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-stone-800 dark:text-stone-200">
              <span className="w-6 shrink-0 text-right font-mono text-xs leading-6 text-stone-400">{numbers[i]}</span>
              <span>{highlightTerms(it.text, query)}</span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
