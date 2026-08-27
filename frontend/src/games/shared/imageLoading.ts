import type { RefObject } from "react"
import { useCallback, useEffect, useReducer, useRef } from "react"

// Per-attempt budget for a photo to either paint or fail. Short on purpose: a retry re-requests
// the same URL, so the browser serves whatever it already holds (its own HTTP cache, or the
// service worker's Cache Storage) and resolves instantly - only the first attempt pays for the
// network. See useImageLoad's docstring for why retrying is what actually fixes this.
export const IMAGE_TIMEOUT_MS = 8_000

// One initial load plus two automatic retries. Past that the player gets a visible error with a
// button instead of a fourth silent attempt.
export const MAX_IMAGE_ATTEMPTS = 3

export type ImageLoadStatus = "loading" | "loaded" | "failed"

export interface ImageLoadState {
  status: ImageLoadStatus
  // How many attempts have been spent, 0-based - the retry budget, capped by MAX_IMAGE_ATTEMPTS.
  attempt: number
  // Bumped on every fresh start (automatic retry or manual). Drives the <img>'s `key`, which is
  // what actually forces a new element; kept separate from `attempt` so that a manual retry, which
  // resets the budget to 0, still produces a key nobody has seen before.
  generation: number
}

export type ImageLoadAction =
  // A new photo, or a manual retry: start over with a full budget.
  | { type: "reset" }
  | { type: "loaded" }
  // The <img> fired onError, or this attempt ran out of time. Both mean "this element is not going
  // to paint", and both spend one attempt from the same budget.
  | { type: "attemptFailed" }

export const initialImageLoadState: ImageLoadState = { status: "loading", attempt: 0, generation: 0 }

// Kept pure and outside the hook so the transitions are testable without a DOM - the DOM-dependent
// half (is this image already decoded? has this attempt run out of time?) lives in useImageLoad and
// only ever *dispatches* into this.
export function imageLoadReducer(state: ImageLoadState, action: ImageLoadAction): ImageLoadState {
  switch (action.type) {
    case "reset":
      // Idempotent on a state that's already a fresh first attempt - the mount-time reset below
      // must not bump `generation` and remount the very element whose request just started.
      if (state.status === "loading" && state.attempt === 0) return state
      return { status: "loading", attempt: 0, generation: state.generation + 1 }
    case "loaded":
      return { ...state, status: "loaded" }
    case "attemptFailed": {
      // Already resolved one way or the other - a late timeout firing after the photo painted must
      // not knock it back off screen.
      if (state.status !== "loading") return state
      const attempt = state.attempt + 1
      if (attempt >= MAX_IMAGE_ATTEMPTS) return { ...state, status: "failed" }
      return { status: "loading", attempt, generation: state.generation + 1 }
    }
  }
}

export interface ImageLoad {
  status: ImageLoadStatus
  imgRef: RefObject<HTMLImageElement | null>
  // Must be passed to the <img> as `key={imgKey}` - see the docstring below.
  imgKey: string
  onLoad: () => void
  onError: () => void
  retry: () => void
}

function isPainted(img: HTMLImageElement | null): boolean {
  // `complete` alone isn't enough: a *failed* image is complete too, and reports naturalWidth 0.
  return !!img && img.complete && img.naturalWidth > 0
}

// Load/error/retry state for a single <img>, with the one guarantee the raw element can't give:
// it always resolves. A photo either paints, recovers on a retry, or ends up `failed` with
// something the player can act on - it can never sit on a spinner forever.
//
// Two independent failure modes make that necessary, and both were observed on this app's own
// fullscreen photos:
//
//   - The response never reaches the element. A stalled connection fires neither `load` nor
//     `error`, and with a service worker in front (src/sw.ts) the element is waiting on
//     respondWith() rather than on a socket, so it loses even the browser's own network timeout.
//     `imgKey` is the answer: changing an <img>'s key mounts a fresh element, which is the only
//     thing that makes the browser deliver the resource again - reassigning `src` to the value it
//     already has does nothing at all. The retried URL is deliberately identical, with no
//     cache-busting, because the copy the browser or the service worker already holds is exactly
//     what makes a retry instant.
//   - The `load` event is missed. React attaches onLoad during commit and this hook's own reset
//     runs in a passive effect after it, so a photo already in cache can fire `load` in between and
//     the state meaning "painted" is lost while the pixels sit right there. `isPainted` covers that
//     with no network at all, and is checked *before* every retry - so the common recovery costs
//     one DOM read rather than a request.
export function useImageLoad(src: string): ImageLoad {
  const [state, dispatch] = useReducer(imageLoadReducer, initialImageLoadState)
  const imgRef = useRef<HTMLImageElement>(null)

  // A new photo starts over - but only after checking whether the element we were handed is
  // already showing it. Blindly resetting to "loading" here is what used to strand an
  // already-decoded cached photo behind a permanent spinner.
  useEffect(() => {
    dispatch(isPainted(imgRef.current) ? { type: "loaded" } : { type: "reset" })
  }, [src])

  // One timer per attempt - `generation` is a dependency so every retry gets its own fresh budget,
  // and `status` so a resolved photo stops arming timers.
  useEffect(() => {
    if (state.status !== "loading") return
    const timer = setTimeout(() => {
      dispatch(isPainted(imgRef.current) ? { type: "loaded" } : { type: "attemptFailed" })
    }, IMAGE_TIMEOUT_MS)
    return () => clearTimeout(timer)
  }, [src, state.generation, state.status])

  const onLoad = useCallback(() => dispatch({ type: "loaded" }), [])
  const onError = useCallback(() => dispatch({ type: "attemptFailed" }), [])
  const retry = useCallback(() => dispatch({ type: "reset" }), [])

  return {
    status: state.status,
    imgRef,
    imgKey: `${src}#${state.generation}`,
    onLoad,
    onError,
    retry,
  }
}
