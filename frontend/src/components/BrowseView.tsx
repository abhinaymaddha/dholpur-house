import { Loader2, Search, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useDebounce } from '../hooks/useDebounce'
import { getFacets, searchTranscripts } from '../services/api'
import { emptyFilters, type Facets, type Filters, type SearchHit, type SortOrder, type Stats } from '../types'
import { AskPanel } from './AskPanel'
import { FacetSidebar } from './FacetSidebar'
import { TranscriptCard } from './TranscriptCard'

const PAGE = 24

/** Browse: keyword search plus drill-down by year → board and tags, then open transcripts to read. */
export function BrowseView({ stats, askOpen, onAskOpen, onOpen }: {
  stats: Stats | null
  askOpen: boolean
  onAskOpen: (open: boolean) => void
  onOpen: (id: string, query: string) => void
}) {
  const [q, setQ] = useState('')
  const query = useDebounce(q.trim(), 300)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [sort, setSort] = useState<SortOrder>('relevance')
  const [facets, setFacets] = useState<Facets | null>(null)
  const [hits, setHits] = useState<SearchHit[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    let stale = false
    setLoading(true)
    Promise.all([getFacets(filters, query), searchTranscripts(query, filters, 0, PAGE, sort)])
      .then(([f, r]) => { if (!stale) { setFacets(f); setHits(r.hits); setTotal(r.total) } })
      .finally(() => { if (!stale) setLoading(false) })
    return () => { stale = true }
  }, [query, filters, sort])

  // "Newest first" is a separate option only while searching; without keywords relevance already means newest.
  useEffect(() => { if (!query && sort === 'recent') setSort('relevance') }, [query, sort])

  const loadMore = async () => {
    setLoading(true)
    try {
      const r = await searchTranscripts(query, filters, hits.length, PAGE, sort)
      setHits((h) => [...h, ...r.hits])
    } finally {
      setLoading(false)
    }
  }

  const active = activeChips(filters)

  return (
    <div className="grid gap-6 md:grid-cols-[260px_1fr]">
      <aside className={`${showFilters ? 'block' : 'hidden'} md:block md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:self-start md:overflow-y-auto md:pr-2`}>
        <FacetSidebar facets={facets} filters={filters} onChange={setFilters} />
      </aside>

      <section className="min-w-0 space-y-3">
        <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-400" size={18} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder='Search transcripts, e.g. "cooperative federalism", Kota coaching, chess -cricket'
            className="h-11 w-full rounded-lg border border-slate-300 bg-white pr-10 pl-10 text-[15px] shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none dark:border-slate-700 dark:bg-slate-900"
          />
          {q && (
            <button aria-label="Clear search" onClick={() => setQ('')} className="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={16} />
            </button>
          )}
        </div>
        <button onClick={() => onAskOpen(!askOpen)} aria-pressed={askOpen}
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium transition ${askOpen
            ? 'border-indigo-600 bg-indigo-600 text-white'
            : 'border-indigo-200 bg-white text-indigo-700 hover:border-indigo-400 dark:border-indigo-900 dark:bg-slate-900 dark:text-indigo-300'}`}>
          <Sparkles size={15} /> Ask AI
        </button>
        </div>

        {askOpen && (
          <AskPanel filters={filters} q={query} stats={stats} onOpen={onOpen} onClose={() => onAskOpen(false)}
            scope={total === (stats?.transcripts ?? -1) ? `all ${total.toLocaleString()} transcripts`
              : `the ${total.toLocaleString()} transcript${total === 1 ? '' : 's'} matching your search and filters`} />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowFilters(!showFilters)}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm md:hidden dark:border-slate-700">
              <SlidersHorizontal size={14} /> Filters{active.length ? ` (${active.length})` : ''}
            </button>
            <span className="text-sm text-slate-500">
              {total.toLocaleString()} {query ? 'matching ' : ''}transcript{total === 1 ? '' : 's'}
            </span>
            {loading && <Loader2 size={15} className="animate-spin text-slate-400" />}
          </div>
          <select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value as SortOrder)}
            className="h-8 rounded-md border border-slate-300 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <option value="relevance">{query ? 'Best match' : 'Newest first'}</option>
            {query && <option value="recent">Newest first</option>}
            <option value="questions">Most questions</option>
            <option value="marks">Highest PT marks</option>
          </select>
        </div>

        {active.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {active.map((c) => (
              <button key={c.label} onClick={() => setFilters(c.remove(filters))}
                className="inline-flex items-center gap-1 rounded-full bg-indigo-600 py-1 pr-2 pl-3 text-xs font-medium text-white hover:bg-indigo-700">
                {c.label} <X size={12} />
              </button>
            ))}
            <button onClick={() => setFilters(emptyFilters())} className="text-xs text-indigo-600 hover:underline dark:text-indigo-400">Clear all</button>
          </div>
        )}

        <ul className="grid gap-3 lg:grid-cols-2">
          {hits.map((h) => (
            <li key={h.id}>
              <TranscriptCard t={h} snippet={query ? h.snippet : undefined} onOpen={() => onOpen(h.id, query)} />
            </li>
          ))}
        </ul>
        {!loading && hits.length === 0 && (
          <p className="py-10 text-center text-slate-500">No transcripts match. Try fewer words or remove a filter.</p>
        )}
        {hits.length < total && (
          <div className="text-center">
            <button onClick={loadMore} disabled={loading}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-900">
              Load more
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

function activeChips(f: Filters): { label: string; remove: (f: Filters) => Filters }[] {
  const chips: { label: string; remove: (f: Filters) => Filters }[] = []
  if (f.cse_year) chips.push({ label: `CSE ${f.cse_year}`, remove: (x) => ({ ...x, cse_year: '', board: '' }) })
  if (f.board) chips.push({ label: f.board, remove: (x) => ({ ...x, board: '' }) })
  if (f.exam) chips.push({ label: f.exam, remove: (x) => ({ ...x, exam: '' }) })
  if (f.background) chips.push({ label: f.background, remove: (x) => ({ ...x, background: '' }) })
  if (f.optional_tag) chips.push({ label: `Optional: ${f.optional_tag}`, remove: (x) => ({ ...x, optional_tag: '' }) })
  if (f.state) chips.push({ label: f.state, remove: (x) => ({ ...x, state: '' }) })
  if (f.interest) chips.push({ label: f.interest, remove: (x) => ({ ...x, interest: '' }) })
  for (const t of f.topics) chips.push({ label: t, remove: (x) => ({ ...x, topics: x.topics.filter((y) => y !== t) }) })
  if (f.has_marks) chips.push({ label: 'PT marks reported', remove: (x) => ({ ...x, has_marks: false }) })
  return chips
}
