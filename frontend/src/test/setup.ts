// Global test setup, run once per test file before the file's own imports run.
//
// Registers jest-dom's matchers (toBeInTheDocument, toHaveTextContent, ...) on vitest's `expect`.
// Harmless in the default `node` environment - it only extends `expect`, it doesn't touch the DOM.
import "@testing-library/jest-dom/vitest"
