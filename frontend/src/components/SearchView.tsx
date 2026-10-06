import { Loader2, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useDebounce } from '../hooks/useDebounce'
import { formatDate, Snippet } from '../lib/text'
import { searchTranscripts } from '../services/api'
import type { Filters, SearchHit, Stats } from '../types'
import { FiltersBar } from './FiltersBar'
import { MetaLine } from './MetaLine'

const PAGE = 20

export function SearchView({ stats, onOpen }: { stats: Stats | null; onOpen: (id: string, query: string) => void }) {
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<Filters>({ board: '', cse_year: '', exam: '' })
  const [hits, setHits] = useState<SearchHit[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const query = useDebounce(q, 300)

  useEffect(() => {
    let stale = false
    setLoading(true)
    setError('')
    searchTranscripts(query, filters, 0, PAGE)
      .then((r) => { if (!stale) { setHits(r.hits); setTotal(r.total) } })
      .catch(() => { if (!stale) setError('Search failed. Is the API running?') })
      .finally(() => { if (!stale) setLoading(false) })
    return () => { stale = true }
  }, [query, filters])

  const loadMore = async () => {
    setLoading(true)
    try {
      const r = await searchTranscripts(query, filters, hits.length, PAGE)
      setHits((h) => [...h, ...r.hits])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-400" size={18} />
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder='Search transcripts, e.g. "cooperative federalism", Kota coaching, chess -cricket'
          className="h-11 w-full rounded-lg border border-slate-300 bg-white pr-10 pl-10 text-[15px] shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none dark:border-slate-700 dark:bg-slate-900"
        />
        {loading && <Loader2 className="absolute top-1/2 right-3 -translate-y-1/2 animate-spin text-slate-400" size={18} />}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <FiltersBar stats={stats} filters={filters} onChange={setFilters} />
        <span className="text-sm text-slate-500">
          {total.toLocaleString()} {query ? 'matching' : ''} transcript{total === 1 ? '' : 's'}
        </span>
      </div>
      {error && <p className="text-red-600">{error}</p>}
      <ul className="space-y-3">
        {hits.map((h) => (
          <li key={h.id}>
            <button
              onClick={() => onOpen(h.id, query)}
              className="w-full rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-indigo-700"
            >
              <div className="mb-1.5 flex items-baseline justify-between gap-3">
                <span className="truncate font-medium">{h.alias || 'Anonymous candidate'}</span>
                <span className="shrink-0 text-xs text-slate-400">{formatDate(h.posted_at)}</span>
              </div>
              <MetaLine t={h} />
              {h.daf && <p className="mt-2 line-clamp-1 text-sm text-slate-500 dark:text-slate-400">DAF: {h.daf}</p>}
              <p className="mt-2 line-clamp-3 text-sm whitespace-pre-line text-slate-700 dark:text-slate-300">
                <Snippet text={h.snippet} />
              </p>
            </button>
          </li>
        ))}
      </ul>
      {!loading && !error && hits.length === 0 && (
        <p className="py-10 text-center text-slate-500">No transcripts match. Try fewer or different words.</p>
      )}
      {hits.length < total && (
        <div className="text-center">
          <button onClick={loadMore} disabled={loading} className="rounded-md border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-900">
            Load more
          </button>
        </div>
      )}
    </div>
  )
}
