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
  background: string[]
  optional_tag: string | null
  states: string[]
  interests: string[]
  topics: string[]
  question_count: number
}

export interface OutlineItem {
  kind: 'q' | 'note'
  text: string
}

export interface OutlineSection {
  title: string
  member: string | null
  gender: 'male' | 'female' | 'unknown'
  items: OutlineItem[]
}

export interface Outline {
  header: ({ key: string; value: string } | { text: string })[]
  sections: OutlineSection[]
}

export interface Transcript extends TranscriptMeta {
  text: string
  message_ids: number[]
  duplicates: string[]
  structure: Outline | null
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
  background: string
  optional_tag: string
  state: string
  interest: string
  topics: string[]
  has_marks: boolean
}

export const emptyFilters = (): Filters => ({
  board: '', cse_year: '', exam: '', background: '', optional_tag: '', state: '', interest: '', topics: [], has_marks: false,
})

export interface Facets {
  total: number
  tree: { year: number; count: number; boards: FacetCount[] }[]
  exam: FacetCount[]
  background: FacetCount[]
  optional_tag: FacetCount[]
  state: FacetCount[]
  interest: FacetCount[]
  topic: FacetCount[]
  has_marks: number
}

export type SortOrder = 'relevance' | 'recent' | 'questions' | 'marks'

export interface Source extends TranscriptMeta {
  score: number
  excerpts: { section: string; text: string }[]
}

// ---------- Interview mode ----------

export interface InterviewTopic {
  name: string
  source: 'past' | 'current' | 'mixed' | 'daf'
  past_questions: number
  recent_articles: number
}

export interface InterviewFilters {
  topics: string[]
  board: string
  daf: string
  source: 'auto' | 'past' | 'current'
}

export interface Evaluation {
  scores: Record<string, number>
  average: number
  verdict: 'good' | 'partial' | 'weak'
  critique: string
  missing_points: string[]
  model_answer_points: string[]
  skipped?: boolean
}

export interface Turn {
  id: number
  main_index: number
  depth: number
  topic: string
  question: string
  source: {
    type: 'past' | 'current' | 'daf' | 'followup'
    transcript_id?: string
    board?: string
    cse_year?: number
    url?: string
    title?: string
    publisher?: string
    published_at?: string
    daf_item?: string
  }
  answer: string | null
  evaluation: Evaluation | null
  mode: string | null
}

export interface InterviewReport {
  answered: number
  skipped: number
  average: number
  verdicts: Record<'good' | 'partial' | 'weak', number>
  dimensions: Record<string, number>
  topics: { topic: string; answered: number; average: number }[]
  turns: Turn[]
}
