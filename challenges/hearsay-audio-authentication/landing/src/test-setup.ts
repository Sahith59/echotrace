import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

Element.prototype.scrollIntoView = vi.fn()
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as unknown as typeof HTMLCanvasElement.prototype.getContext

class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = NoopObserver as unknown as typeof ResizeObserver
globalThis.IntersectionObserver = NoopObserver as unknown as typeof IntersectionObserver
window.matchMedia = window.matchMedia ?? ((query: string) => ({
  matches: false, media: query, onchange: null,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false,
})) as unknown as typeof window.matchMedia
