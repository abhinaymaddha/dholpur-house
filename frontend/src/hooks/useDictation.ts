import { useCallback, useEffect, useState } from 'react'
import { Dictation } from '../lib/speech'

/** Dictate into a text box: `onText` receives the whole text as it is spoken. */
export function useDictation(onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const [dictation] = useState(() => new Dictation(onText, (err) => { setListening(false); setError(err ?? '') }))
  useEffect(() => () => dictation.stop(), [dictation])

  const start = useCallback((base: string) => { setError(''); setListening(true); dictation.start(base) }, [dictation])
  const stop = useCallback(() => { dictation.stop(); setListening(false) }, [dictation])
  return { listening, error, start, stop }
}
