import type { TranscriptMeta } from '../types'

export function MetaLine({ t }: { t: TranscriptMeta }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-500 dark:text-stone-400">
      <span className="rounded bg-stone-100 px-1.5 py-0.5 font-medium text-stone-700 dark:bg-stone-800 dark:text-stone-200">{t.board}</span>
      <span>CSE {t.cse_year}{t.exam !== 'CSE' && ` · ${t.exam}`}</span>
      {t.interview_date && <span>{t.interview_date}</span>}
      {t.optional_subject && <span>Optional: {t.optional_subject}</span>}
      {t.pt_marks && <span className="font-medium text-lawn-700 dark:text-lawn-400">PT {t.pt_marks}</span>}
    </div>
  )
}
