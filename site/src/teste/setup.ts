import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { limparCache } from '../dados'
import { servir } from './exemplos'

beforeEach(() => {
  limparCache()
  servir()
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
