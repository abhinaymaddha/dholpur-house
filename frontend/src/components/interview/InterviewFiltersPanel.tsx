import { Newspaper } from 'lucide-react'
import type { InterviewFilters, InterviewTopic, Stats } from '../../types'

const GROUPS: { label: string; hint: string; match: (t: InterviewTopic) => boolean }[] = [
  { label: 'Current affairs + past interviews', hint: 'Questions from recent news and from past boards', match: (t) => t.source === 'mixed' || t.source === 'current' },
  { label: 'Past interviews', hint: 'Real questions boards have asked', match: (t) => t.source === 'past' },
  { label: 'Your DAF', hint: 'Questions on your own background', match: (t) => t.source === 'daf' },
]

/** Left rail of Interview mode. Changes apply from the next question; no need to restart. */
export function InterviewFiltersPanel({ topics, stats, filters, onChange }: {
  topics: InterviewTopic[]
  stats: Stats | null
  filters: InterviewFilters
  onChange: (f: InterviewFilters) => void
}) {
  const set = (patch: Partial<InterviewFilters>) => onChange({ ...filters, ...patch })
  const toggle = (name: string) =>
    set({ topics: filters.topics.includes(name) ? filters.topics.filter((t) => t !== name) : [...filters.topics, name] })
  const dafChosen = filters.topics.includes('DAF & Background')

  return (
    <div className="space-y-5 text-sm">
      <p className="text-xs text-slate-500 dark:text-slate-400">Changes apply from the next question.</p>
      {GROUPS.map((g) => {
        const items = topics.filter(g.match)
        if (!items.length) return null
        return (
          <section key={g.label}>
            <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">{g.label}</h3>
            <p className="mb-2 text-xs text-slate-400">{g.hint}</p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((t) => {
                const on = filters.topics.includes(t.name)
                return (
                  <button key={t.name} onClick={() => toggle(t.name)}
                    title={`${t.past_questions} past questions${t.recent_articles ? ` · ${t.recent_articles} recent articles` : ''}`}
                    className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition ${on
                      ? 'border-indigo-500 bg-indigo-600 text-white'
                      : 'border-slate-200 text-slate-700 hover:border-indigo-400 dark:border-slate-700 dark:text-slate-300'}`}>
                    {t.name}
                    {t.recent_articles > 0 && t.source !== 'past' && <Newspaper size={11} className={on ? 'text-indigo-200' : 'text-slate-400'} />}
                  </button>
                )
              })}
            </div>
          </section>
        )
      })}

      <section>
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">Question source</h3>
        <div className="flex rounded-md border border-slate-200 p-0.5 text-xs dark:border-slate-700">
          {([['auto', 'Auto'], ['past', 'Past interviews'], ['current', 'Current affairs']] as const).map(([v, label]) => (
            <button key={v} onClick={() => set({ source: v })}
              className={`flex-1 rounded px-2 py-1 ${filters.source === v ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900' : 'text-slate-600 dark:text-slate-400'}`}>
              {label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-slate-400">Auto mixes per topic: news-heavy topics lean on current affairs.</p>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">Board style</h3>
        <select value={filters.board} onChange={(e) => set({ board: e.target.value })}
          className="h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900">
          <option value="">Any board</option>
          {stats?.boards.filter((b) => b.value !== 'Unknown').map((b) => <option key={b.value} value={b.value}>{b.value}</option>)}
        </select>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
          Your DAF {dafChosen ? '' : <span className="font-normal normal-case">(optional)</span>}
        </h3>
        <textarea value={filters.daf} onChange={(e) => set({ daf: e.target.value })} rows={4}
          placeholder="Hometown, state, education, job, hobbies… e.g. Kota, Rajasthan; B.Tech IIT Roorkee; PSIR; chess, cycling"
          className={`w-full resize-y rounded-md border bg-white p-2 text-sm dark:bg-slate-900 ${dafChosen && !filters.daf.trim()
            ? 'border-amber-400' : 'border-slate-300 dark:border-slate-700'}`} />
        {dafChosen && !filters.daf.trim() && <p className="text-xs text-amber-600">Needed for “Your DAF” questions.</p>}
      </section>
    </div>
  )
}
