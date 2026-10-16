import { Check, ChevronDown, ChevronRight } from 'lucide-react'
import { useState, type Dispatch, type SetStateAction } from 'react'
import type { FacetCount, Facets, Filters } from '../types'

type SingleKey = 'background' | 'optional_tag' | 'state' | 'interest'

const GROUPS: { key: SingleKey; facet: keyof Facets; label: string }[] = [
  { key: 'background', facet: 'background', label: 'Background' },
  { key: 'optional_tag', facet: 'optional_tag', label: 'Optional subject' },
  { key: 'state', facet: 'state', label: 'Home state' },
  { key: 'interest', facet: 'interest', label: 'DAF interests' },
]

/** Left rail of the Browse view: exam year → board tree, then tag groups with live counts. */
export function FacetSidebar({ facets, filters, onChange }: {
  facets: Facets | null
  filters: Filters
  onChange: Dispatch<SetStateAction<Filters>>
}) {
  // Functional updates, so two quick changes can't overwrite each other.
  const set = (patch: Partial<Filters>) => onChange((f) => ({ ...f, ...patch }))
  const toggleTopic = (t: string) => onChange((f) => ({
    ...f, topics: f.topics.includes(t) ? f.topics.filter((x) => x !== t) : [...f.topics, t],
  }))

  return (
    <nav className="space-y-5 text-sm">
      <section>
        <Heading>Exam year &amp; board</Heading>
        <ul className="space-y-0.5">
          {facets?.tree.map((y) => (
            <YearNode
              key={y.year}
              year={y.year}
              count={y.count}
              boards={y.boards}
              filters={filters}
              onYear={() => set({ cse_year: filters.cse_year === String(y.year) && !filters.board ? '' : String(y.year), board: '' })}
              onBoard={(b) => set(filters.board === b && filters.cse_year === String(y.year)
                ? { board: '' } : { cse_year: String(y.year), board: b })}
            />
          ))}
        </ul>
      </section>

      <section>
        <Heading>Topics asked</Heading>
        <p className="mb-1.5 text-xs text-stone-400">Pick several to narrow down</p>
        <div className="flex flex-wrap gap-1.5">
          {facets?.topic.map((t) => {
            const on = filters.topics.includes(t.value)
            return (
              <button
                key={t.value}
                onClick={() => toggleTopic(t.value)}
                className={`rounded-full border px-2.5 py-1 text-xs transition ${on
                  ? 'border-teak-500 bg-teak-600 text-white'
                  : 'border-stone-200 text-stone-700 hover:border-teak-400 dark:border-stone-700 dark:text-stone-300'}`}
              >
                {t.value} <span className={on ? 'text-teak-200' : 'text-stone-400'}>{t.count}</span>
              </button>
            )
          })}
        </div>
      </section>

      {GROUPS.map((g) => (
        <FacetGroup
          key={g.key}
          label={g.label}
          values={(facets?.[g.facet] as FacetCount[] | undefined) ?? []}
          selected={filters[g.key]}
          onSelect={(v) => set({ [g.key]: filters[g.key] === v ? '' : v } as Partial<Filters>)}
        />
      ))}

      <section>
        <Heading>More</Heading>
        <label className="flex cursor-pointer items-center gap-2 text-stone-700 dark:text-stone-300">
          <input type="checkbox" checked={filters.has_marks} onChange={(e) => set({ has_marks: e.target.checked })} className="accent-sandstone-600" />
          PT marks reported <span className="text-stone-400">{facets?.has_marks ?? ''}</span>
        </label>
        {(facets?.exam.length ?? 0) > 1 && (
          <div className="mt-2 flex gap-1.5">
            {facets!.exam.map((x) => (
              <button key={x.value} onClick={() => set({ exam: filters.exam === x.value ? '' : x.value })}
                className={`rounded-md border px-2 py-0.5 text-xs ${filters.exam === x.value ? 'border-sandstone-500 bg-sandstone-50 text-sandstone-700 dark:bg-sandstone-500/10 dark:text-sandstone-300' : 'border-stone-200 text-stone-600 dark:border-stone-700 dark:text-stone-400'}`}>
                {x.value} {x.count}
              </button>
            ))}
          </div>
        )}
      </section>
    </nav>
  )
}

function Heading({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase dark:text-stone-400">{children}</h3>
}

function Row({ label, count, active, onClick, indent = false }: {
  label: string; count: number; active: boolean; onClick: () => void; indent?: boolean
}) {
  return (
    <button onClick={onClick}
      className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-left ${indent ? 'pl-7' : ''} ${active
        ? 'bg-sandstone-50 font-medium text-sandstone-700 dark:bg-sandstone-500/10 dark:text-sandstone-300'
        : 'text-stone-700 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800'}`}>
      <span className="flex items-center gap-1.5 truncate">{active && <Check size={13} />}{label}</span>
      <span className="text-xs text-stone-400">{count}</span>
    </button>
  )
}

function YearNode({ year, count, boards, filters, onYear, onBoard }: {
  year: number; count: number; boards: FacetCount[]; filters: Filters; onYear: () => void; onBoard: (b: string) => void
}) {
  const inYear = filters.cse_year === String(year)
  const [open, setOpen] = useState(true)
  return (
    <li>
      <div className="flex items-center">
        <button aria-label={open ? 'Collapse' : 'Expand'} onClick={() => setOpen(!open)} className="p-1 text-stone-400">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <div className="flex-1"><Row label={`CSE ${year}`} count={count} active={inYear && !filters.board} onClick={onYear} /></div>
      </div>
      {open && (
        <ul>
          {boards.map((b) => (
            <li key={b.value}>
              <Row label={b.value} count={b.count} indent active={inYear && filters.board === b.value} onClick={() => onBoard(b.value)} />
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function FacetGroup({ label, values, selected, onSelect }: {
  label: string; values: FacetCount[]; selected: string; onSelect: (v: string) => void
}) {
  const [all, setAll] = useState(false)
  if (!values.length) return null
  const shown = all ? values : values.slice(0, 6)
  return (
    <section>
      <Heading>{label}</Heading>
      <ul className="space-y-0.5">
        {shown.map((v) => (
          <li key={v.value}><Row label={v.value} count={v.count} active={selected === v.value} onClick={() => onSelect(v.value)} /></li>
        ))}
      </ul>
      {values.length > 6 && (
        <button onClick={() => setAll(!all)} className="mt-1 px-2 text-xs text-sandstone-600 hover:underline dark:text-sandstone-400">
          {all ? 'Show less' : `Show all ${values.length}`}
        </button>
      )}
    </section>
  )
}
