import { afterEach, describe, expect, it, vi } from 'vitest'
import { FakeRecognition, installSpeech } from '../test/speech'
import { canListen, canSpeak, Dictation, speak, stopSpeaking } from './speech'

afterEach(() => vi.unstubAllGlobals())

describe('without browser support', () => {
  it('reports no support, finishes at once and explains why dictation is unavailable', () => {
    expect(canSpeak()).toBe(false)
    expect(canListen()).toBe(false)
    const onEnd = vi.fn()
    speak('Hello', onEnd)
    stopSpeaking()
    expect(onEnd).toHaveBeenCalledOnce()
    const onStop = vi.fn()
    new Dictation(vi.fn(), onStop).start('')
    expect(onStop).toHaveBeenCalledWith(expect.stringMatching(/Chrome, Edge or Safari/))
  })
})

describe('speak', () => {
  it('prefers an Indian English voice and replaces anything already being read', () => {
    const s = installSpeech({ voices: [{ lang: 'en-US', name: 'US' }, { lang: 'en_IN', name: 'Indian' }] })
    const onEnd = vi.fn()
    speak('What is GDP?', onEnd)
    expect(s.synth.cancel).toHaveBeenCalled()
    expect(s.last()).toMatchObject({ text: 'What is GDP?', voice: { name: 'Indian' }, lang: 'en_IN' })
    s.finish()
    expect(onEnd).toHaveBeenCalledOnce()
    s.last().onerror?.()
    expect(onEnd).toHaveBeenCalledTimes(2)
    stopSpeaking()
    expect(s.synth.cancel).toHaveBeenCalledTimes(2)
  })

  it('falls back to British, then any English, then the default voice', () => {
    let s = installSpeech({ voices: [{ lang: 'en-US', name: 'US' }, { lang: 'en-GB', name: 'UK' }] })
    speak('a')
    expect(s.last().voice).toMatchObject({ name: 'UK' })
    s = installSpeech({ voices: [{ lang: 'fr-FR', name: 'FR' }, { lang: 'en-US', name: 'US' }] })
    speak('b')
    expect(s.last().voice).toMatchObject({ name: 'US' })
    s = installSpeech({ voices: [] })
    speak('c')
    expect(s.last()).toMatchObject({ voice: null, lang: 'en-IN' })
    s.finish()   // no onEnd given
  })
})

describe('Dictation', () => {
  it('builds on the existing text, keeps going across pauses and stops on request', () => {
    installSpeech()
    const onText = vi.fn()
    const onStop = vi.fn()
    const d = new Dictation(onText, onStop)
    d.start('I think')
    const first = FakeRecognition.last
    expect(first).toMatchObject({ lang: 'en-IN', continuous: true, interimResults: true, started: true })
    expect(d.listening).toBe(true)
    first.say(['federalism', true], [' is cooperative', false])
    expect(onText).toHaveBeenLastCalledWith('I think federalism is cooperative')
    first.say(['federalism', true], ['is cooperative', true])
    first.end()                                    // the browser stopped after a pause: restart
    const second = FakeRecognition.last
    expect(second).not.toBe(first)
    expect(second.started).toBe(true)
    second.say(['and fiscal', true])
    expect(onText).toHaveBeenLastCalledWith('I think federalism is cooperative and fiscal')
    d.stop()
    expect(d.listening).toBe(false)
    expect(FakeRecognition.instances).toHaveLength(2)
    expect(onStop).not.toHaveBeenCalled()
  })

  it('ignores harmless errors, reports blocking ones and finishes when the browser ends a stopped run', () => {
    installSpeech()
    const onStop = vi.fn()
    const d = new Dictation(vi.fn(), onStop)
    d.start('')
    FakeRecognition.last.fail('no-speech')          // silence: restarts
    expect(FakeRecognition.instances).toHaveLength(2)
    FakeRecognition.last.fail('not-allowed')
    expect(onStop).toHaveBeenCalledWith(expect.stringMatching(/Microphone access is blocked/))
    expect(d.listening).toBe(false)
    expect(FakeRecognition.instances).toHaveLength(2)

    d.start('')
    const rec = FakeRecognition.last
    ;(d as unknown as { wanted: boolean }).wanted = false   // as after stop(), before the browser's onend
    rec.end()
    expect(onStop).toHaveBeenLastCalledWith()
  })
})
