// Global test setup, run once per test file before the file's own imports run.
//
// Registers jest-dom's matchers (toBeInTheDocument, toHaveTextContent, ...) on vitest's `expect`.
// Harmless in the default `node` environment - it only extends `expect`, it doesn't touch the DOM.
import "@testing-library/jest-dom/vitest"

import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

// Unmounts whatever a jsdom test rendered after each test - without this, a test file with more
// than one render() call (any component test beyond the single-render smoke test) leaves every
// previous render's DOM behind, so a later `getByRole` can match more than one element. No-op in
// the default `node` environment (nothing was ever mounted into a document there).
afterEach(cleanup)

// jsdom doesn't implement ResizeObserver - several components track their own rendered size with
// it directly (games/shared/useElementSize.ts, games/Dateguessr/TimelineRuler.tsx's own inline
// one), which throws on mount without this. A no-op stub is enough: none of those components'
// *tests* assert on a real resize, just on rendering without crashing. Guarded on `window` so this
// stays a no-op in the default `node` environment, same as the jest-dom import above.
if (typeof window !== "undefined") {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  window.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
}
