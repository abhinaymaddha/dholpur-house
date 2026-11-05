/**
 * Voice interviews with the browser's own speech features, so no audio reaches our server:
 * the board's questions are read aloud with speechSynthesis, and answers are dictated with
 * SpeechRecognition (Chrome, Edge and Safari; Chrome sends the audio to Google to transcribe).
 */

const LANG = 'en-IN'

interface RecognitionAlternative { transcript: string }
interface RecognitionResult { isFinal: boolean; 0: RecognitionAlternative }
interface RecognitionEvent { results: ArrayLike<RecognitionResult> }
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: RecognitionEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export const canSpeak = (): boolean => 'speechSynthesis' in window
export const canListen = (): boolean => Boolean(recognitionCtor())

/** An Indian English voice if the device has one, else British, else any English voice. */
function pickVoice(): SpeechSynthesisVoice | undefined {
  const voices = speechSynthesis.getVoices()
  return voices.find((v) => v.lang.replace('_', '-') === LANG)
    ?? voices.find((v) => v.lang.replace('_', '-') === 'en-GB')
    ?? voices.find((v) => v.lang.startsWith('en'))
}

/** Read text aloud, replacing anything already being read. `onEnd` runs when it finishes or fails. */
export function speak(text: string, onEnd?: () => void): void {
  if (!canSpeak()) { onEnd?.(); return }
  speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const voice = pickVoice()
  if (voice) u.voice = voice
  u.lang = voice?.lang ?? LANG
  u.rate = 0.95
  u.onend = () => onEnd?.()
  u.onerror = () => onEnd?.()
  speechSynthesis.speak(u)
}

export function stopSpeaking(): void {
  if (canSpeak()) speechSynthesis.cancel()
}

const join = (...parts: string[]) => parts.map((p) => p.trim()).filter(Boolean).join(' ')

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access is blocked. Allow it in your browser\'s site settings, or type your answer.',
  'service-not-allowed': 'This browser won\'t transcribe speech here. Type your answer, or try Chrome, Edge or Safari.',
  'audio-capture': 'No microphone was found.',
  network: 'Speech recognition needs an internet connection.',
}

/**
 * Dictation into a text box. Browsers end recognition after a pause, so it restarts until stop() is called;
 * `onText` always receives the whole text: what was there before, plus everything said so far.
 */
export class Dictation {
  private rec: Recognition | null = null
  private wanted = false
  private base = ''
  private committed = ''
  private readonly onText: (text: string) => void
  private readonly onStop: (error?: string) => void

  constructor(onText: (text: string) => void, onStop: (error?: string) => void) {
    this.onText = onText
    this.onStop = onStop
  }

  get listening(): boolean { return this.wanted }

  start(base: string): void {
    const Ctor = recognitionCtor()
    if (!Ctor) { this.onStop(ERRORS['service-not-allowed']); return }
    this.stop()
    this.wanted = true
    this.base = base
    this.committed = ''
    this.run(Ctor)
  }

  stop(): void {
    this.wanted = false
    const rec = this.rec
    this.rec = null                           // first, so its onend knows it was stopped on purpose
    rec?.stop()
  }

  private run(Ctor: RecognitionCtor): void {
    const rec = new Ctor()
    rec.lang = LANG
    rec.continuous = true
    rec.interimResults = true
    let final = ''
    rec.onresult = (e) => {
      final = ''
      let interim = ''
      for (const r of Array.from(e.results)) {
        if (r.isFinal) final = join(final, r[0].transcript)
        else interim = join(interim, r[0].transcript)
      }
      this.onText(join(this.base, this.committed, final, interim))
    }
    rec.onerror = (e) => {
      const message = ERRORS[e.error]
      if (!message) return                    // no-speech, aborted: onend restarts or finishes
      this.wanted = false
      this.rec = null
      this.onStop(message)
    }
    rec.onend = () => {
      this.committed = join(this.committed, final)
      if (this.rec !== rec) return            // stopped or restarted meanwhile
      if (this.wanted) { this.run(Ctor); return }
      this.rec = null
      this.onStop()
    }
    this.rec = rec
    rec.start()
  }
}
