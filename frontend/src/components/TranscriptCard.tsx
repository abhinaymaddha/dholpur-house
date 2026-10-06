import { MessageCircleQuestion } from 'lucide-react'
import { formatDate, Snippet } from '../lib/text'
import type { TranscriptMeta } from '../types'
import { MetaLine } from './MetaLine'

const chip = 'rounded-full px-2 py-0.5 text-[11px] font-medium'

export function TagChips({ t, max = 4 }: { t: TranscriptMeta; max?: number }) {
  const profile = [...t.background, ...(t.optional_tag ? [`Opt: ${t.optional_tag}`] : []), ...t.states]
  const topics = t.topics.slice(0, max)
  return (
    <div className="flex flex-wrap gap-1">
      {profile.map((p) => (
        <span key={p} className={`${chip} bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300`}>{p}</span>
      ))}
      {topics.map((p) => (
        <span key={p} className={`${chip} bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300`}>{p}</span>
      ))}
      {t.topics.length > max && <span className={`${chip} text-slate-400`}>+{t.topics.length - max}</span>}
    </div>
  )
}

export function TranscriptCard({ t, snippet, onOpen }: { t: TranscriptMeta; snippet?: string; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-700"
    >
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="truncate font-medium">{t.alias || 'Anonymous candidate'}</span>
        <span className="flex shrink-0 items-center gap-3 text-xs text-slate-400">
          {t.question_count > 0 && (
            <span className="inline-flex items-center gap-1"><MessageCircleQuestion size={13} />{t.question_count}</span>
          )}
          {formatDate(t.posted_at)}
        </span>
      </div>
      <MetaLine t={t} />
      {t.daf && <p className="mt-2 line-clamp-1 text-sm text-slate-500 dark:text-slate-400">DAF: {t.daf}</p>}
      <div className="mt-2"><TagChips t={t} /></div>
      {snippet && (
        <p className="mt-2 line-clamp-3 text-sm whitespace-pre-line text-slate-700 dark:text-slate-300">
          <Snippet text={snippet} />
        </p>
      )}
    </button>
  )
}
