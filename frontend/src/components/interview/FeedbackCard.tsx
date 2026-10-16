import type { Evaluation, EvaluationIssue } from '../../types'

const VERDICT = {
  good: { label: 'Good', cls: 'bg-lawn-100 text-lawn-800 dark:bg-lawn-500/15 dark:text-lawn-300' },
  partial: { label: 'Partial', cls: 'bg-brass-100 text-brass-800 dark:bg-brass-500/15 dark:text-brass-300' },
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
          <span className="w-20 shrink-0 text-stone-500 capitalize dark:text-stone-400">{k}</span>
          <div className="h-1.5 flex-1 rounded-full bg-stone-200 dark:bg-stone-700">
            <div className={`h-1.5 rounded-full ${v >= 4 ? 'bg-lawn-500' : v >= 3 ? 'bg-brass-500' : 'bg-rose-500'}`} style={{ width: `${v * 20}%` }} />
          </div>
          <span className="w-3 text-right text-stone-500">{v}</span>
        </div>
      ))}
    </div>
  )
}

const ISSUE_LABEL: Record<EvaluationIssue['type'], { label: string; cls: string }> = {
  factual_error: { label: 'Factual error', cls: 'bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300' },
  unsupported_claim: { label: 'Unsupported', cls: 'bg-brass-100 text-brass-800 dark:bg-brass-500/15 dark:text-brass-300' },
  vague: { label: 'Vague', cls: 'bg-brass-100 text-brass-800 dark:bg-brass-500/15 dark:text-brass-300' },
  off_topic: { label: 'Off-topic', cls: 'bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-300' },
  missing_perspective: { label: 'One-sided', cls: 'bg-iron-100 text-iron-800 dark:bg-iron-500/15 dark:text-iron-300' },
  impractical: { label: 'Impractical', cls: 'bg-brass-100 text-brass-800 dark:bg-brass-500/15 dark:text-brass-300' },
  tone: { label: 'Tone', cls: 'bg-teak-100 text-teak-800 dark:bg-teak-500/15 dark:text-teak-300' },
  structure: { label: 'Structure', cls: 'bg-stone-200 text-stone-700 dark:bg-stone-700 dark:text-stone-200' },
}

function Issue({ i }: { i: EvaluationIssue }) {
  const tag = ISSUE_LABEL[i.type] ?? ISSUE_LABEL.structure
  return (
    <li className="space-y-1 rounded-md border border-stone-200 bg-white p-3 dark:border-stone-700 dark:bg-stone-900">
      <div className="flex flex-wrap items-start gap-2">
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] font-semibold ${tag.cls}`}>{tag.label}</span>
        {i.quote
          ? <q className="text-stone-800 italic dark:text-stone-200">{i.quote}</q>
          : <span className="text-stone-500 italic">Missing from your answer</span>}
      </div>
      <p className="text-stone-700 dark:text-stone-300">{i.why}</p>
      {i.fix && <p className="text-stone-600 dark:text-stone-400"><span className="font-medium text-lawn-700 dark:text-lawn-400">Better: </span>{i.fix}</p>}
    </li>
  )
}

/** The board's critique of one answer. */
export function FeedbackCard({ e, followUpNext }: { e: Evaluation; followUpNext: boolean }) {
  return (
    <div className="space-y-3 rounded-lg border border-stone-200 bg-stone-50 p-4 text-sm dark:border-stone-800 dark:bg-stone-900/60">
      <div className="flex flex-wrap items-center gap-2">
        <VerdictPill verdict={e.verdict} average={e.average} />
        <span className="text-xs text-stone-500">
          {followUpNext ? 'Good enough for a follow-up' : e.verdict === 'good' ? 'Moving to a new question' : 'No follow-up: moving on'}
        </span>
      </div>
      <ScoreBars scores={e.scores} />
      <p className="leading-relaxed text-stone-800 dark:text-stone-200">{e.critique}</p>
      {(e.issues?.length ?? 0) > 0 && (
        <div>
          <h4 className="mb-1.5 text-xs font-semibold text-stone-500 uppercase">Where it went wrong</h4>
          <ul className="space-y-2">{e.issues!.map((i, n) => <Issue key={n} i={i} />)}</ul>
        </div>
      )}
      {(e.strengths?.length ?? 0) > 0 && (
        <p className="text-stone-600 dark:text-stone-400">
          <span className="font-medium text-lawn-700 dark:text-lawn-400">What worked: </span>{e.strengths!.join(' · ')}
        </p>
      )}
      {e.missing_points.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-semibold text-stone-500 uppercase">Missing</h4>
          <ul className="list-disc space-y-0.5 pl-5 text-stone-700 dark:text-stone-300">
            {e.missing_points.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </div>
      )}
      {e.model_answer_points.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-semibold text-sandstone-600 uppercase dark:text-sandstone-400">What a strong answer covers</summary>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-stone-700 dark:text-stone-300">
            {e.model_answer_points.map((p, i) => <li key={i}>{p}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
