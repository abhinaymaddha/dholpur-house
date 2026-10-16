import { FolderTree, GraduationCap } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { BrowseView } from './components/BrowseView'
import { InterviewView } from './components/interview/InterviewView'
import { TranscriptPanel } from './components/TranscriptPanel'
import { getStats } from './services/api'
import type { Stats } from './types'

type Tab = 'browse' | 'interview'

const tabFromHash = (): Tab => {
  const h = window.location.hash.slice(1)
  return h === 'interview' ? h : 'browse'   // old #search / #ask links land on Browse
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash)
  const [stats, setStats] = useState<Stats | null>(null)
  const [open, setOpen] = useState<{ id: string; query: string } | null>(null)
  const [askOpen, setAskOpen] = useState(() => window.location.hash === '#ask')

  useEffect(() => {
    getStats().then(setStats).catch(() => setStats(null))
    const onHash = () => {
      setTab(tabFromHash()); setOpen(null)
      if (window.location.hash === '#ask') setAskOpen(true)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const openTranscript = useCallback((id: string, query: string) => setOpen({ id, query }), [])
  const closeTranscript = useCallback(() => setOpen(null), [])

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-4">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-semibold tracking-tight"><img src="/favicon.svg" alt="" className="h-6 w-6" />Dholpur House</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {stats ? `UPSC interview prep · ${stats.transcripts.toLocaleString()} real Personality Test transcripts` : 'UPSC interview prep from real Personality Test transcripts'}
            </p>
          </div>
          <nav className="flex rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
            <TabButton active={tab === 'browse'} href="#browse" icon={<FolderTree size={15} />} label="Browse" />
            <TabButton active={tab === 'interview'} href="#interview" icon={<GraduationCap size={15} />} label="Interview" />
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {stats?.transcripts === 0 && (
          <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Transcripts are still being loaded (this takes a few minutes on first start). Refresh shortly.
          </p>
        )}
        {tab === 'browse' && <BrowseView stats={stats} askOpen={askOpen} onAskOpen={setAskOpen} onOpen={openTranscript} />}
        {tab === 'interview' && <InterviewView stats={stats} onOpen={openTranscript} />}
      </main>

      <footer className="mx-auto max-w-6xl space-y-1 px-4 pb-8 text-xs text-slate-400">
        <p>
          All transcripts come from the Telegram channel{' '}
          <a href="https://t.me/csetranscripts" target="_blank" rel="noreferrer" className="underline hover:text-indigo-600">
            Interview Transcripts (CSPT-2026)
          </a>
          . Full credit to its admins and to the candidates who shared their experiences. Want something removed?{' '}
          <a href="https://github.com/abhinaymaddha/dholpur-house/issues" target="_blank" rel="noreferrer" className="underline hover:text-indigo-600">
            Get in touch
          </a>
          .
        </p>
        <p>Transcripts are candidates' own recollections. AI answers and feedback may be wrong — check the sources.</p>
      </footer>

      {open && <TranscriptPanel id={open.id} query={open.query} onClose={closeTranscript} />}
    </div>
  )
}

function TabButton({ active, href, icon, label }: { active: boolean; href: string; icon: React.ReactNode; label: string }) {
  return (
    <a
      href={href}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition ${
        active ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-white' : 'text-slate-600 hover:text-slate-900 dark:text-slate-400'
      }`}
    >
      {icon}
      {label}
    </a>
  )
}
