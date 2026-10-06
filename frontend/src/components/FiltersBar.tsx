import { emptyFilters, type Filters, type Stats } from '../types'

const select =
  'h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none ' +
  'dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'

export function FiltersBar({ stats, filters, onChange }: {
  stats: Stats | null
  filters: Filters
  onChange: (f: Filters) => void
}) {
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement>) => onChange({ ...filters, [k]: e.target.value })
  const active = filters.board || filters.cse_year || filters.exam
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select aria-label="Board" className={select} value={filters.board} onChange={set('board')}>
        <option value="">All boards</option>
        {stats?.boards.map((b) => (
          <option key={b.value} value={b.value}>{b.value} ({b.count})</option>
        ))}
      </select>
      <select aria-label="Exam year" className={select} value={filters.cse_year} onChange={set('cse_year')}>
        <option value="">All years</option>
        {stats?.years.map((y) => (
          <option key={y.value} value={y.value}>CSE {y.value} ({y.count})</option>
        ))}
      </select>
      <select aria-label="Exam" className={select} value={filters.exam} onChange={set('exam')}>
        <option value="">CSE + IFoS</option>
        {stats?.exams.map((x) => (
          <option key={x.value} value={x.value}>{x.value} ({x.count})</option>
        ))}
      </select>
      {active && (
        <button className="text-sm text-indigo-600 hover:underline dark:text-indigo-400" onClick={() => onChange(emptyFilters())}>
          Clear filters
        </button>
      )}
    </div>
  )
}
