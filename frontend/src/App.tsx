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
    <div className="flex min-h-screen flex-col bg-stone-50 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <div className="tiranga h-[6px]" aria-hidden="true" />
      <header className="cornice relative overflow-hidden bg-stone-50 dark:bg-stone-900">
        <div className="jali pointer-events-none absolute inset-y-0 right-0 hidden w-72 text-sandstone-700 sm:block dark:text-sandstone-300" aria-hidden="true" />
        <div className="relative mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-5">
          <div>
            <h1 className="wordmark flex items-center gap-2.5 text-xl text-sandstone-800 dark:text-sandstone-200">
              <img src="/favicon.svg" alt="" className="h-8 w-8" />Dholpur House
            </h1>
            <p className="mt-0.5 text-sm text-stone-600 dark:text-stone-400">
              {stats ? `UPSC interview prep · ${stats.transcripts.toLocaleString()} real Personality Test transcripts` : 'UPSC interview prep from real Personality Test transcripts'}
            </p>
          </div>
          <nav className="flex gap-1 rounded-md border border-stone-200 bg-white/70 p-1 dark:border-stone-700 dark:bg-stone-800/70">
            <TabButton active={tab === 'browse'} href="#browse" icon={<FolderTree size={15} />} label="Browse" />
            <TabButton active={tab === 'interview'} href="#interview" icon={<GraduationCap size={15} />} label="Interview" />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {stats?.transcripts === 0 && (
          <p className="mb-4 rounded-md border border-brass-200 bg-brass-50 p-3 text-sm text-brass-800 dark:border-brass-900 dark:bg-brass-950 dark:text-brass-200">
            Transcripts are still being loaded (this takes a few minutes on first start). Refresh shortly.
          </p>
        )}
        {tab === 'browse' && <BrowseView stats={stats} askOpen={askOpen} onAskOpen={setAskOpen} onOpen={openTranscript} />}
        {tab === 'interview' && <InterviewView stats={stats} onOpen={openTranscript} />}
      </main>

      <footer className="mt-6 border-t border-stone-200 bg-stone-100/60 dark:border-stone-800 dark:bg-stone-900/60">
        <div className="mx-auto max-w-6xl space-y-3 px-4 py-6 text-xs text-stone-500 dark:text-stone-400">
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="tiranga-row h-1 w-24 rounded-full" aria-hidden="true" />
            <p className="font-display text-sm tracking-wide text-stone-700 dark:text-stone-300">
              In respect for every honest public servant who upholds the nation&rsquo;s integrity and serves it with pride.
            </p>
          </div>
          <p>
            All transcripts come from the Telegram channel{' '}
            <a href="https://t.me/csetranscripts" target="_blank" rel="noreferrer" className="underline hover:text-sandstone-600">
              Interview Transcripts (CSPT-2026)
            </a>
            . Full credit to its admins and to the candidates who shared their experiences. Want something removed?{' '}
            <a href="https://github.com/abhinaymaddha/dholpur-house/issues" target="_blank" rel="noreferrer" className="underline hover:text-sandstone-600">
              Get in touch
            </a>
            .
          </p>
          <p>Transcripts are candidates' own recollections. AI answers and feedback may be wrong — check the sources. Not affiliated with the UPSC.</p>
        </div>
      </footer>

      {open && <TranscriptPanel id={open.id} query={open.query} onClose={closeTranscript} />}
    </div>
  )
}

function TabButton({ active, href, icon, label }: { active: boolean; href: string; icon: React.ReactNode; label: string }) {
  return (
    <a
      href={href}
      aria-current={active ? 'page' : undefined}
      className={`inline-flex items-center gap-1.5 rounded-sm px-3.5 py-1.5 text-sm font-medium tracking-wide uppercase transition ${
        active ? 'bg-sandstone-600 text-stone-50 shadow-sm' : 'text-stone-600 hover:bg-stone-100 hover:text-sandstone-700 dark:text-stone-300 dark:hover:bg-stone-700'
      }`}
    >
      {icon}
      {label}
    </a>
  )
}
