export interface TranscriptMeta {
  id: string
  board: string
  alias: string | null
  interview_date: string | null
  daf: string | null
  optional_subject: string | null
  pt_marks: number | null
  exam: string
  cse_year: number
  posted_at: string
  telegram_url: string
}

export interface Transcript extends TranscriptMeta {
  text: string
  message_ids: number[]
  duplicates: string[]
}

export interface SearchHit extends TranscriptMeta {
  snippet: string
  rank: number | null
}

export interface SearchResponse {
  total: number
  hits: SearchHit[]
}

export interface FacetCount {
  value: string
  count: number
}

export interface Stats {
  transcripts: number
  held: number
  chunks: number
  boards: FacetCount[]
  years: FacetCount[]
  exams: FacetCount[]
  llm_model: string
}

export interface Filters {
  board: string
  cse_year: string
  exam: string
}

export interface Source extends TranscriptMeta {
  score: number
  excerpts: { section: string; text: string }[]
}
