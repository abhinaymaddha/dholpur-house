import type { Evaluation, Facets, InterviewTopic, Source, Stats, Transcript, TranscriptMeta, Turn } from '../types'

export const meta = (over: Partial<TranscriptMeta> = {}): TranscriptMeta => ({
  id: 'u1', board: 'Sanjay Verma', alias: 'Static', interview_date: '08/01/2025', daf: 'Haryana, IIT, Gita',
  optional_subject: 'Maths', pt_marks: 187, exam: 'CSE', cse_year: 2024, posted_at: '2025-01-11T09:00:00',
  telegram_url: 'https://t.me/csetranscripts/11', background: ['Engineering'], optional_tag: 'Mathematics',
  states: ['Haryana'], interests: [], topics: ['Ethics & Values', 'Economy', 'Polity', 'Health', 'Sports'],
  question_count: 13, ...over,
})

export const transcript = (over: Partial<Transcript> = {}): Transcript => ({
  ...meta(), text: 'Chairman\nWhy do you read the Gita?\nM1\nWhat is dharma?', message_ids: [11, 12], duplicates: [],
  structure: {
    header: [{ key: 'Board', value: 'Sanjay Verma' }, { text: 'Forenoon session' }],
    sections: [
      { title: 'Chairman', member: 'Chairperson', gender: 'male', items: [{ kind: 'q', text: 'Why do you read the Gita?' }] },
      { title: 'M2 (lady)', member: 'Member 2', gender: 'female',
        items: [{ kind: 'note', text: 'She smiled' }, { kind: 'q', text: 'What is dharma?' }] },
      { title: 'Feedback', member: null, gender: 'unknown', items: [{ kind: 'note', text: 'Went well overall' }] },
    ],
  },
  ...over,
})

export const stats: Stats = {
  transcripts: 4, held: 1, chunks: 20, llm_model: 'test-model',
  boards: [{ value: 'Sanjay Verma', count: 2 }, { value: 'Unknown', count: 1 }, { value: 'BB Swain', count: 1 }],
  years: [{ value: '2024', count: 3 }], exams: [{ value: 'CSE', count: 4 }],
}

export const facets = (over: Partial<Facets> = {}): Facets => ({
  total: 4,
  tree: [{ year: 2025, count: 3, boards: [{ value: 'BB Swain', count: 2 }, { value: 'Sanjay Verma', count: 1 }] },
         { year: 2024, count: 1, boards: [{ value: 'Sanjay Verma', count: 1 }] }],
  exam: [{ value: 'CSE', count: 3 }, { value: 'IFoS', count: 1 }],
  background: [{ value: 'Engineering', count: 2 }],
  optional_tag: [{ value: 'Mathematics', count: 1 }],
  state: Array.from({ length: 8 }, (_, i) => ({ value: `State ${i + 1}`, count: 8 - i })),
  interest: [],
  topic: [{ value: 'Economy', count: 3 }, { value: 'Health', count: 2 }],
  has_marks: 2,
  ...over,
})

export const source = (over: Partial<Source> = {}): Source => ({
  ...meta(), score: 0.03, excerpts: [{ section: 'Chairman', text: 'Why do you read the Gita?' }], ...over,
})

export const evaluation = (over: Partial<Evaluation> = {}): Evaluation => ({
  scores: { relevance: 4, accuracy: 4, depth: 3, balance: 2 }, average: 3.25, verdict: 'partial',
  issues: [
    { quote: 'it is always good', type: 'vague', why: 'No reason given.', fix: 'Say why.' },
    { quote: null, type: 'missing_perspective', why: 'Ignores farmers.', fix: '' },
    { quote: 'x', type: 'unknown' as never, why: 'Odd type.', fix: 'f' },
  ],
  strengths: ['Clear opening'], critique: 'A fair start but thin.', missing_points: ['Federal angle'],
  model_answer_points: ['Define the term'], ...over,
})

export const topics: InterviewTopic[] = [
  { name: 'Economy', news: true, needs_daf: false, past_questions: 30, recent_articles: 4 },
  { name: 'Ethics & Values', news: false, needs_daf: false, past_questions: 20, recent_articles: 0 },
  { name: 'DAF & Background', news: false, needs_daf: true, past_questions: 10, recent_articles: 0 },
]

export const turn = (over: Partial<Turn> = {}): Turn => ({
  id: 1, main_index: 1, depth: 0, topic: 'Economy', question: 'What is GDP?',
  source: { type: 'past', transcript_id: 'u1', board: 'Sanjay Verma', cse_year: 2024 },
  answer: null, evaluation: null, mode: null, ...over,
})
