import { ExternalLink, Loader2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { highlightTerms } from '../lib/text'
import { getTranscript } from '../services/api'
import type { Transcript } from '../types'
import { MetaLine } from './MetaLine'

/** Slide-over reader for one full transcript. */
export function TranscriptPanel({ id, query, onClose }: { id: string; query: string; onClose: () => void }) {
  const [t, setT] = useState<Transcript | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setT(null)
    setError('')
    getTranscript(id).then(setT).catch(() => setError('Could not load this transcript.'))
  }, [id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-xl dark:bg-slate-950">
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="min-w-0 space-y-1">
            <h2 className="truncate text-lg font-semibold">{t?.alias || 'Anonymous candidate'}</h2>
            {t && <MetaLine t={t} />}
          </div>
          <button aria-label="Close" onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X size={20} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {error && <p className="text-red-600">{error}</p>}
          {!t && !error && <Loader2 className="animate-spin text-slate-400" />}
          {t && (
            <>
              {t.daf && (
                <p className="mb-3 rounded-md bg-slate-50 p-3 text-sm dark:bg-slate-900">
                  <span className="font-medium">DAF: </span>{t.daf}
                </p>
              )}
              <pre className="font-sans text-[15px] leading-relaxed whitespace-pre-wrap text-slate-800 dark:text-slate-200">
                {highlightTerms(t.text, query)}
              </pre>
            </>
          )}
        </div>
        {t && (
          <footer className="flex items-center justify-between border-t border-slate-200 p-3 text-xs text-slate-500 dark:border-slate-800">
            <span>Shared on Telegram · {t.message_ids.length > 1 ? `${t.message_ids.length} messages joined` : 'single message'}</span>
            <a href={t.telegram_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400">
              Original post <ExternalLink size={12} />
            </a>
          </footer>
        )}
      </aside>
    </div>
  )
}
