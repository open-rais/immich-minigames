// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, renderHook } from "@testing-library/react"

import {
  IMAGE_TIMEOUT_MS,
  MAX_IMAGE_ATTEMPTS,
  imageLoadReducer,
  initialImageLoadState,
  useImageLoad,
} from "./imageLoading"
import type { ImageLoadState } from "./imageLoading"

const loading = (attempt: number, generation: number): ImageLoadState => ({
  status: "loading",
  attempt,
  generation,
})

describe("imageLoadReducer", () => {
  it("leaves a fresh first attempt untouched on reset", () => {
    // The mount-time reset lands here, and must not bump `generation` - that would remount the
    // very element whose request has just started.
    expect(imageLoadReducer(initialImageLoadState, { type: "reset" })).toBe(initialImageLoadState)
  })

  it("spends one attempt and asks for a new element each time one fails", () => {
    const afterFirst = imageLoadReducer(initialImageLoadState, { type: "attemptFailed" })

    expect(afterFirst).toEqual(loading(1, 1))
    expect(imageLoadReducer(afterFirst, { type: "attemptFailed" })).toEqual(loading(2, 2))
  })

  it("gives up only once the whole budget is spent", () => {
    let state = initialImageLoadState
    for (let i = 0; i < MAX_IMAGE_ATTEMPTS - 1; i++) {
      state = imageLoadReducer(state, { type: "attemptFailed" })
      expect(state.status).toBe("loading")
    }

    expect(imageLoadReducer(state, { type: "attemptFailed" }).status).toBe("failed")
  })

  it("ignores a failure once the photo has painted", () => {
    // A timer armed for an attempt can fire just after its own onLoad landed; honouring it would
    // pull a photo that's already on screen back off it.
    const loaded = imageLoadReducer(initialImageLoadState, { type: "loaded" })

    expect(imageLoadReducer(loaded, { type: "attemptFailed" })).toBe(loaded)
  })

  it("hands a manual retry a generation nobody has seen, even though the budget resets to 0", () => {
    let state = initialImageLoadState
    for (let i = 0; i < MAX_IMAGE_ATTEMPTS; i++) {
      state = imageLoadReducer(state, { type: "attemptFailed" })
    }
    expect(state.status).toBe("failed")

    const retried = imageLoadReducer(state, { type: "reset" })

    expect(retried.attempt).toBe(0)
    expect(retried.status).toBe("loading")
    // The whole point: a key the <img> hasn't been mounted under before.
    expect(retried.generation).toBeGreaterThan(state.generation)
  })
})

describe("useImageLoad", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // The hook only ever reads `complete`/`naturalWidth` off the element, so a stand-in is enough -
  // jsdom never actually loads an image.
  function attachImage(
    result: { current: ReturnType<typeof useImageLoad> },
    { painted }: { painted: boolean },
  ) {
    result.current.imgRef.current = {
      complete: painted,
      naturalWidth: painted ? 800 : 0,
    } as HTMLImageElement
  }

  it("remounts the element when an attempt runs out of time", () => {
    const { result } = renderHook(() => useImageLoad("/photo.jpg"))
    const firstKey = result.current.imgKey
    attachImage(result, { painted: false })

    act(() => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
    })

    expect(result.current.status).toBe("loading")
    expect(result.current.imgKey).not.toBe(firstKey)
  })

  it("recovers a photo that already painted, without asking for a new element", () => {
    // The missed-`load` case: the pixels are there, only the state saying so was lost.
    const { result } = renderHook(() => useImageLoad("/photo.jpg"))
    const firstKey = result.current.imgKey
    attachImage(result, { painted: true })

    act(() => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
    })

    expect(result.current.status).toBe("loaded")
    expect(result.current.imgKey).toBe(firstKey)
  })

  it("fails only after the whole budget of attempts has timed out", () => {
    const { result } = renderHook(() => useImageLoad("/photo.jpg"))
    attachImage(result, { painted: false })

    for (let i = 0; i < MAX_IMAGE_ATTEMPTS - 1; i++) {
      act(() => {
        vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
      })
      expect(result.current.status).toBe("loading")
    }
    act(() => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
    })

    expect(result.current.status).toBe("failed")
  })

  it("stops arming timers once the photo is loaded", () => {
    const { result } = renderHook(() => useImageLoad("/photo.jpg"))
    act(() => {
      result.current.onLoad()
    })

    act(() => {
      vi.advanceTimersByTime(IMAGE_TIMEOUT_MS * MAX_IMAGE_ATTEMPTS * 2)
    })

    expect(result.current.status).toBe("loaded")
  })

  it("treats a new src as already loaded when the element is showing it", () => {
    // A cached photo can fire `load` before this hook's own reset runs; resetting blindly is what
    // used to strand it behind a permanent spinner.
    const { result, rerender } = renderHook(({ src }) => useImageLoad(src), {
      initialProps: { src: "/one.jpg" },
    })
    act(() => {
      result.current.onLoad()
    })
    attachImage(result, { painted: true })

    rerender({ src: "/two.jpg" })

    expect(result.current.status).toBe("loaded")
  })

  it("starts over for a new src the element has not painted", () => {
    const { result, rerender } = renderHook(({ src }) => useImageLoad(src), {
      initialProps: { src: "/one.jpg" },
    })
    act(() => {
      result.current.onLoad()
    })
    attachImage(result, { painted: false })

    rerender({ src: "/two.jpg" })

    expect(result.current.status).toBe("loading")
    expect(result.current.imgKey).toContain("/two.jpg")
  })

  it("retry() puts a failed photo back to loading on a brand-new element", () => {
    const { result } = renderHook(() => useImageLoad("/photo.jpg"))
    attachImage(result, { painted: false })
    for (let i = 0; i < MAX_IMAGE_ATTEMPTS; i++) {
      act(() => {
        vi.advanceTimersByTime(IMAGE_TIMEOUT_MS)
      })
    }
    expect(result.current.status).toBe("failed")
    const failedKey = result.current.imgKey

    act(() => {
      result.current.retry()
    })

    expect(result.current.status).toBe("loading")
    expect(result.current.imgKey).not.toBe(failedKey)
  })
})
