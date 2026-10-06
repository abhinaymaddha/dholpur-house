import type { ReactNode } from 'react'

// Must match HL_START / HL_END in backend/app/services/search.py
const HL = /⟦(.*?)⟧/gs

/** Render a backend snippet: plain text with highlight markers turned into <mark>. No HTML is injected. */
export function Snippet({ text }: { text: string }) {
  const parts: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(HL)) {
    parts.push(text.slice(last, m.index))
    parts.push(<mark key={m.index}>{m[1]}</mark>)
    last = m.index! + m[0].length
  }
  parts.push(text.slice(last))
  return <>{parts}</>
}

/** Highlight the query's words inside a full transcript. */
export function highlightTerms(text: string, query: string): ReactNode {
  const words = query
    .replace(/["()-]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 2 && w.toLowerCase() !== 'or')
    .map((w) => w.replace(/[.*+?^${}|[\]\\]/g, '\\$&'))
  if (!words.length) return text
  const re = new RegExp(`(${words.join('|')})`, 'gi')
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))
}

/** Inline markdown subset for answers: **bold** and [S1] citations (some models write 【S1】). */
function inline(text: string, onCite: (n: number) => void, keyBase: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /\*\*(.+?)\*\*|[[【]S(\d+)[\]】]/g
  let last = 0
  for (const m of text.matchAll(re)) {
    out.push(text.slice(last, m.index))
    if (m[1] !== undefined) out.push(<strong key={`${keyBase}-${m.index}`}>{m[1]}</strong>)
    else {
      const n = Number(m[2])
      out.push(
        <button
          key={`${keyBase}-${m.index}`}
          onClick={() => onCite(n)}
          className="mx-0.5 rounded bg-indigo-100 px-1.5 py-px align-baseline text-xs font-semibold text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-500/20 dark:text-indigo-300"
        >
          S{n}
        </button>,
      )
    }
    last = m.index! + m[0].length
  }
  out.push(text.slice(last))
  return out
}

/** Block markdown subset for answers: headings, bullet/numbered lists, paragraphs. */
export function Answer({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: ReactNode[] } | null = null
  const flush = () => {
    if (!list) return
    const cls = 'my-2 space-y-1 pl-5 ' + (list.ordered ? 'list-decimal' : 'list-disc')
    blocks.push(list.ordered ? <ol key={blocks.length} className={cls}>{list.items}</ol> : <ul key={blocks.length} className={cls}>{list.items}</ul>)
    list = null
  }
  text.split('\n').forEach((line, i) => {
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    const heading = /^#{1,4}\s+(.*)$/.exec(line)
    if (bullet || numbered) {
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) { flush(); list = { ordered, items: [] } }
      list.items.push(<li key={i}>{inline((bullet || numbered)![1], onCite, `l${i}`)}</li>)
      return
    }
    flush()
    if (heading) blocks.push(<h4 key={i} className="mt-4 mb-1 font-semibold">{inline(heading[1], onCite, `h${i}`)}</h4>)
    else if (line.trim()) blocks.push(<p key={i} className="my-2">{inline(line, onCite, `p${i}`)}</p>)
  })
  flush()
  return <div className="leading-relaxed">{blocks}</div>
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
