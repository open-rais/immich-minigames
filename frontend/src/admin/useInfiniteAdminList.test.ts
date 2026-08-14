// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { useInfiniteAdminList } from "./useInfiniteAdminList"

// The hook only uses t() for its generic error fallback, so the stub returns the key itself.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}))

const PAGE_SIZE = 2

// jsdom reports 0 for every layout measurement, so the scroll container is faked explicitly.
// Tests that don't attach one leave containerRef null, which switches the auto-continue effect off
// and lets loadMore/reload be exercised on their own.
function fakeContainer(scrollHeight: number, clientHeight: number) {
  const el = document.createElement("div")
  Object.defineProperty(el, "scrollHeight", { value: scrollHeight })
  Object.defineProperty(el, "clientHeight", { value: clientHeight })
  return el as HTMLDivElement
}

function scrollEvent(scrollHeight: number, scrollTop: number, clientHeight: number) {
  return {
    currentTarget: { scrollHeight, scrollTop, clientHeight },
  } as unknown as React.UIEvent<HTMLDivElement>
}

const page = (from: number, size: number) =>
  Array.from({ length: size }, (_, i) => `row-${from + i}`)

function render(
  fetchPage: (offset: number, limit: number) => Promise<string[]>,
  container?: HTMLDivElement,
) {
  return renderHook(() => {
    const list = useInfiniteAdminList(fetchPage, PAGE_SIZE)
    // Assigned during render so it is in place before the auto-continue effect runs.
    if (container) list.containerRef.current = container
    return list
  })
}

describe("the first page", () => {
  it("is requested exactly once on mount", async () => {
    const fetchPage = vi.fn().mockResolvedValue(page(0, 1))
    const { result } = render(fetchPage)

    await waitFor(() => expect(result.current.items).toEqual(["row-0"]))
    expect(fetchPage).toHaveBeenCalledTimes(1)
    expect(fetchPage).toHaveBeenCalledWith(0, PAGE_SIZE)
  })

  it("starts as null so the caller can tell loading apart from empty", async () => {
    const fetchPage = vi.fn().mockResolvedValue([])
    const { result } = render(fetchPage)

    expect(result.current.items).toBeNull()
    await waitFor(() => expect(result.current.items).toEqual([]))
  })
})

describe("hasMore", () => {
  it("is false once a page comes back shorter than the page size", async () => {
    const { result } = render(vi.fn().mockResolvedValue(page(0, 1)))
    await waitFor(() => expect(result.current.items).toHaveLength(1))
    expect(result.current.hasMore).toBe(false)
  })

  it("stays true while pages come back full", async () => {
    const { result } = render(vi.fn().mockResolvedValue(page(0, PAGE_SIZE)))
    await waitFor(() => expect(result.current.items).toHaveLength(PAGE_SIZE))
    expect(result.current.hasMore).toBe(true)
  })
})

describe("loadMore", () => {
  it("appends the next page and keeps advancing the offset", async () => {
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))

    await act(async () => {
      result.current.onScroll(scrollEvent(100, 100, 100))
    })
    expect(fetchPage).toHaveBeenLastCalledWith(2, PAGE_SIZE)
    expect(result.current.items).toEqual(["row-0", "row-1", "row-2", "row-3"])

    await act(async () => {
      result.current.onScroll(scrollEvent(100, 100, 100))
    })
    expect(fetchPage).toHaveBeenLastCalledWith(4, PAGE_SIZE)
    expect(result.current.items).toHaveLength(6)
  })

  it("fetches the same page twice when two scroll events land in the same tick", async () => {
    // Documentation of a real hole, not an endorsement: `loadingMore` is React state, so two
    // onScroll calls before the next render both read it as false and both fetch offset 2 - the
    // rows come back duplicated. Momentum scrolling on a phone produces exactly that burst.
    // useGuardedRequests solves the identical problem for game actions with a ref; the same fix
    // (a ref mirror of loadingMore, like the fetchPageRef this file already keeps) applies here.
    // When that lands, this test should be inverted to assert a single fetch.
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))

    await act(async () => {
      result.current.onScroll(scrollEvent(100, 100, 100))
      result.current.onScroll(scrollEvent(100, 100, 100))
    })

    expect(fetchPage.mock.calls).toEqual([
      [0, PAGE_SIZE],
      [2, PAGE_SIZE],
      [2, PAGE_SIZE],
    ])
    expect(result.current.items).toEqual(["row-0", "row-1", "row-2", "row-3", "row-2", "row-3"])
  })

  it("does nothing once there is nothing left to load", async () => {
    const fetchPage = vi.fn().mockResolvedValue(page(0, 1))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.hasMore).toBe(false))

    await act(async () => {
      result.current.onScroll(scrollEvent(100, 100, 100))
    })

    expect(fetchPage).toHaveBeenCalledTimes(1)
  })
})

describe("onScroll", () => {
  it("loads the next page within 48px of the bottom", async () => {
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))

    // 500 - 405 - 100 = -5px left: inside the threshold.
    await act(async () => {
      result.current.onScroll(scrollEvent(500, 405, 100))
    })

    expect(fetchPage).toHaveBeenCalledTimes(2)
  })

  it("does nothing while the bottom is still far away", async () => {
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))

    // 500 - 100 - 100 = 300px left: well outside the threshold.
    await act(async () => {
      result.current.onScroll(scrollEvent(500, 100, 100))
    })

    expect(fetchPage).toHaveBeenCalledTimes(1)
  })
})

describe("reload", () => {
  it("goes back to the first page and replaces instead of appending", async () => {
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))
    await act(async () => {
      result.current.onScroll(scrollEvent(100, 100, 100))
    })
    expect(result.current.items).toHaveLength(4)

    await act(async () => {
      result.current.reload()
    })

    expect(fetchPage).toHaveBeenLastCalledWith(0, PAGE_SIZE)
    expect(result.current.items).toEqual(["row-0", "row-1"])
  })

  it("clears the list while the first page is on its way back", async () => {
    let resolveSecond!: (rows: string[]) => void
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(0, PAGE_SIZE))
      .mockImplementationOnce(() => new Promise((resolve) => (resolveSecond = resolve)))
    const { result } = render(fetchPage)
    await waitFor(() => expect(result.current.items).toHaveLength(2))

    act(() => {
      result.current.reload()
    })
    expect(result.current.items).toBeNull()

    await act(async () => {
      resolveSecond(page(0, 1))
    })
    expect(result.current.items).toEqual(["row-0"])
  })
})

describe("failures", () => {
  it("surfaces the error and stops asking for more", async () => {
    // hasMore going false is what keeps a failing endpoint from being retried in a loop by the
    // auto-continue effect below.
    const fetchPage = vi.fn().mockRejectedValue(new Error("offline"))
    const { result } = render(fetchPage, fakeContainer(100, 100))

    await waitFor(() => expect(result.current.error).toBe("auth.error.generic"))
    expect(result.current.hasMore).toBe(false)
    expect(fetchPage).toHaveBeenCalledTimes(1)
  })
})

describe("the auto-continue effect", () => {
  it("keeps loading while the rows do not fill the container, and stops when they run out", async () => {
    // Regression from 26348b8. This effect has no dependency array, so it re-runs after every
    // render - the test that guarantees it terminates instead of looping forever.
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(0, PAGE_SIZE))
      .mockResolvedValueOnce(page(2, PAGE_SIZE))
      .mockResolvedValueOnce(page(4, 1)) // short page: nothing left
    const { result } = render(fetchPage, fakeContainer(100, 100)) // never overflows

    await waitFor(() => expect(result.current.hasMore).toBe(false))
    expect(fetchPage).toHaveBeenCalledTimes(3)
    expect(result.current.items).toHaveLength(5)

    // Nothing further happens once it has settled.
    await act(async () => {})
    expect(fetchPage).toHaveBeenCalledTimes(3)
  })

  it("stays put once the rows do overflow the container", async () => {
    const fetchPage = vi.fn((offset: number) => Promise.resolve(page(offset, PAGE_SIZE)))
    const { result } = render(fetchPage, fakeContainer(500, 100)) // has something to scroll

    await waitFor(() => expect(result.current.items).toHaveLength(2))
    await act(async () => {})

    expect(fetchPage).toHaveBeenCalledTimes(1)
  })
})
