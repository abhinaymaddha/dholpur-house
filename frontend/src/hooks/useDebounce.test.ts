import { act, renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { useDebounce } from './useDebounce'

it('updates only after the delay', () => {
  vi.useFakeTimers()
  const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), { initialProps: { v: 'a' } })
  rerender({ v: 'ab' })
  expect(result.current).toBe('a')
  act(() => { vi.advanceTimersByTime(300) })
  expect(result.current).toBe('ab')
  vi.useRealTimers()
})
