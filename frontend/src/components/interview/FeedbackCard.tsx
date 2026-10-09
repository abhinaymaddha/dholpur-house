import type { Evaluation } from '../../types'

const VERDICT = {
  good: { label: 'Good', cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300' },
  partial: { label: 'Partial', cls: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300' },
  weak: { label: 'Weak', cls: 'bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300' },
}

export function VerdictPill({ verdict, average }: { verdict: Evaluation['verdict']; average?: number }) {
  const v = VERDICT[verdict]
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${v.cls}`}>
      {v.label}{average !== undefined && ` · ${average.toFixed(1)}/5`}
    </span>
  )
}

export function ScoreBars({ scores }: { scores: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
      {Object.entries(scores).map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 text-xs">
          <span className="w-20 shrink-0 text-slate-500 capitalize dark:text-slate-400">{k}</span>
          <div className="h-1.5 flex-1 rounded-full bg-slate-200 dark:bg-slate-700">
            <div className={`h-1.5 rounded-full ${v >= 4 ? 'bg-emerald-500' : v >= 3 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${v * 20}%` }} />
          </div>
          <span className="w-3 text-right text-slate-500">{v}</span>
        </div>
      ))}
    </div>
  )
}

/** The board's critique of one answer. */
export function FeedbackCard({ e, followUpNext }: { e: Evaluation; followUpNext: boolean }) {
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictPill verdict={e.verdict} average={e.average} />
        <span className="text-xs text-slate-500">
          {followUpNext ? 'Good enough for a follow-up' : e.verdict === 'good' ? 'Moving to a new question' : 'No follow-up: moving on'}
        </span>
      </div>
      <ScoreBars scores={e.scores} />
      <p className="leading-relaxed text-slate-800 dark:text-slate-200">{e.critique}</p>
      {e.missing_points.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-slate-500 uppercase">Missing</h4>
          <ul className="list-disc space-y-0.5 pl-5 text-slate-700 dark:text-slate-300">
            {e.missing_points.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}
      {e.model_answer_points.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-semibold text-indigo-600 uppercase dark:text-indigo-400">What a strong answer covers</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700 dark:text-slate-300">
            {e.model_answer_points.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
