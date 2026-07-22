import { useRef } from "react"
import type { RefObject } from "react"

// Shared re-entrancy guard + staleness token, extracted out of useRoundGame/MoreOrLessGame/
// ImmichdleGame (see CODE-REVIEW.md #18) where the same three refs and the same guard/token
// dance around them were hand-written three times. This owns only that plumbing - callers still
// own their own state updates (busy/phase/etc.), since those genuinely differ per game.
export function useGuardedRequests() {
  // Bumped on every guarded() call and on discardInFlight() (e.g. "Back") - shared across all
  // guarded() calls in a component so that, say, hitting Back while a guess is in flight also
  // invalidates a start that raced in after it. A response for a token that's no longer current is
  // stale and should be ignored when it arrives.
  const requestTokenRef = useRef(0)

  function isCurrent(token: number) {
    return requestTokenRef.current === token
  }

  function discardInFlight() {
    requestTokenRef.current++
  }

  // Wraps an async action with a synchronous re-entrancy guard - a click handler can fire twice
  // before React re-renders, so state alone isn't enough to stop a second network call; `inFlightRef`
  // is checked and set immediately, no render involved. `inFlightRef` is owned by the caller (one per
  // action - e.g. start vs guess - since they don't need to block each other). `run` gets the fresh
  // token so it can call `isCurrent(token)` after each `await` and bail out on a stale response.
  async function guarded(inFlightRef: RefObject<boolean>, run: (token: number) => Promise<void>) {
    if (inFlightRef.current) return
    inFlightRef.current = true
    const token = ++requestTokenRef.current
    try {
      await run(token)
    } finally {
      inFlightRef.current = false
    }
  }

  return { isCurrent, guarded, discardInFlight }
}
