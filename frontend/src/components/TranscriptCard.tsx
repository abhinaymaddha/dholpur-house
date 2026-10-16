import { MessageCircleQuestion } from 'lucide-react'
import { formatDate } from '../lib/format'
import { Snippet } from '../lib/text'
import type { TranscriptMeta } from '../types'
import { MetaLine } from './MetaLine'

const chip = 'rounded-full px-2 py-0.5 text-[11px] font-medium'

export function TagChips({ t, max = 4 }: { t: TranscriptMeta; max?: number }) {
  const profile = [...t.background, ...(t.optional_tag ? [`Opt: ${t.optional_tag}`] : []), ...t.states]
  const topics = t.topics.slice(0, max)
  return (
    <div className="flex flex-wrap gap-1">
      {profile.map((p) => (
        <span key={p} className={`${chip} bg-iron-50 text-iron-700 dark:bg-iron-500/10 dark:text-iron-300`}>{p}</span>
      ))}
      {topics.map((p) => (
        <span key={p} className={`${chip} bg-teak-50 text-teak-700 dark:bg-teak-500/10 dark:text-teak-300`}>{p}</span>
      ))}
      {t.topics.length > max && <span className={`${chip} text-stone-400`}>+{t.topics.length - max}</span>}
    </div>
  )
}

export function TranscriptCard({ t, snippet, onOpen }: { t: TranscriptMeta; snippet?: string; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full rounded-lg border border-stone-200 bg-white p-4 text-left transition hover:border-sandstone-300 hover:shadow-sm dark:border-stone-800 dark:bg-stone-900 dark:hover:border-sandstone-700"
    >
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="truncate font-medium">{t.alias || 'Anonymous candidate'}</span>
        <span className="flex shrink-0 items-center gap-3 text-xs text-stone-400">
          {t.question_count > 0 && (
            <span className="inline-flex items-center gap-1"><MessageCircleQuestion size={13} />{t.question_count}</span>
          )}
          {formatDate(t.posted_at)}
        </span>
      </div>
      <MetaLine t={t} />
      {t.daf && <p className="mt-2 line-clamp-1 text-sm text-stone-500 dark:text-stone-400">DAF: {t.daf}</p>}
      <div className="mt-2"><TagChips t={t} /></div>
      {snippet && (
        <p className="mt-2 line-clamp-3 text-sm whitespace-pre-line text-stone-700 dark:text-stone-300">
          <Snippet text={snippet} />
        </p>
      )}
    </button>
  )
}
