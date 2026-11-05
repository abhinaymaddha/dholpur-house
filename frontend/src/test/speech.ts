import { vi } from 'vitest'

/** A stand-in for the browser's SpeechRecognition: tests drive it with say(), end() and fail(). */
export class FakeRecognition {
  static instances: FakeRecognition[] = []
  static get last(): FakeRecognition { return FakeRecognition.instances[FakeRecognition.instances.length - 1] }
  lang = ''
  continuous = false
  interimResults = false
  started = false
  onresult: ((e: unknown) => void) | null = null
  onerror: ((e: { error: string }) => void) | null = null
  onend: (() => void) | null = null
  constructor() { FakeRecognition.instances.push(this) }
  start() { this.started = true }
  stop() { this.end() }
  abort() { this.end() }
  say(...results: [string, boolean][]) {
    this.onresult?.({ results: results.map(([transcript, isFinal]) => ({ isFinal, 0: { transcript } })) })
  }
  end() { this.started = false; this.onend?.() }
  fail(error: string) { this.onerror?.({ error }); this.end() }
}

class FakeUtterance {
  text: string
  voice: unknown = null
  lang = ''
  rate = 1
  onend: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor(text: string) { this.text = text }
}

/** Install fake speech APIs (jsdom has none). Utterances finish when the test calls finish(). */
export function installSpeech({ listen = true, voices = [{ lang: 'en-IN', name: 'Indian' }] } = {}) {
  FakeRecognition.instances = []
  const queue: FakeUtterance[] = []
  const synth = {
    speak: vi.fn((u: FakeUtterance) => { queue.push(u) }),
    cancel: vi.fn(),
    getVoices: () => voices,
  }
  vi.stubGlobal('speechSynthesis', synth)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  if (listen) vi.stubGlobal('webkitSpeechRecognition', FakeRecognition)
  return {
    synth,
    spoken: () => queue.map((u) => u.text),
    last: () => queue[queue.length - 1],
    finish: () => queue[queue.length - 1]?.onend?.(),
  }
}
