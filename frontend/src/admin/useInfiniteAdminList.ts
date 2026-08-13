import { useEffect, useRef, useState } from "react"
import type { Dispatch, RefObject, SetStateAction } from "react"
import { useTranslation } from "react-i18next"

import { apiErrorMessage } from "../api/errors"

// Load the next page once the list is scrolled to within this many px of the bottom - same
// threshold games/shared/PersonSearchInput.tsx uses for its own infinite-scroll results box.
const SCROLL_THRESHOLD_PX = 48

interface UseInfiniteAdminListResult<T> {
  items: T[] | null // null = first page still loading
  error: string | null
  loadingMore: boolean
  hasMore: boolean
  containerRef: RefObject<HTMLDivElement | null>
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void
  // Exposed for in-place row edit/removal (see AdminUsersSection.tsx/AdminInvitesSection.tsx),
  // same pattern the pre-pagination versions of those sections already used.
  setItems: Dispatch<SetStateAction<T[] | null>>
  // Full reset to page 1 - AdminInvitesSection.tsx needs this after generating a new invite, so
  // the freshly created one (which sorts first) shows up immediately.
  reload: () => void
}

// Generalizes games/shared/PersonSearchInput.tsx's pagination internals (offset tracking,
// hasMore inferred from a short page, threshold-based onScroll, "page didn't even overflow the
// box yet - load another" auto-continue) for any admin list backed by an offset/limit endpoint -
// AdminUsersSection.tsx and AdminInvitesSection.tsx need identical mechanics against different
// endpoints/types, so this is the one place that logic lives rather than duplicated twice.
export function useInfiniteAdminList<T>(
  fetchPage: (offset: number, limit: number) => Promise<T[]>,
  pageSize = 5,
): UseInfiniteAdminListResult<T> {
  const { t } = useTranslation()
  const [items, setItems] = useState<T[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const offsetRef = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)
  // Ref mirror so fetchAndSet/loadMore/reload (stable across renders, nothing re-subscribes to
  // them) always call the latest fetchPage without needing it in a dependency array.
  const fetchPageRef = useRef(fetchPage)
  fetchPageRef.current = fetchPage

  async function fetchAndSet(offset: number, mode: "replace" | "append") {
    setLoadingMore(true)
    setError(null)
    try {
      const page = await fetchPageRef.current(offset, pageSize)
      offsetRef.current = offset + page.length
      setHasMore(page.length === pageSize)
      setItems((prev) => (mode === "append" && prev ? [...prev, ...page] : page))
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("auth.error.generic"))
      setHasMore(false)
    } finally {
      setLoadingMore(false)
    }
  }

  function loadMore() {
    if (loadingMore || !hasMore) return
    void fetchAndSet(offsetRef.current, "append")
  }

  function reload() {
    offsetRef.current = 0
    setItems(null)
    setHasMore(true)
    void fetchAndSet(0, "replace")
  }

  // Fetch the first page once on mount; pageSize/fetchPage changes mid-life aren't a supported use
  // case for either caller.
  useEffect(() => {
    void fetchAndSet(0, "replace")
    // oxlint-disable-next-line
  }, [])

  // A page of pageSize short rows often doesn't overflow the scroll container at all, so onScroll
  // alone would never fire to pull in the next page - keep auto-loading right after each fetch
  // until either the container actually has something to scroll or there's nothing left to fetch.
  // No dependency array (mirrors PersonSearchInput.tsx) - layout needs re-checking after every
  // render, not just when `items` itself changes.
  useEffect(() => {
    const el = containerRef.current
    if (!el || loadingMore || !hasMore || !items) return
    if (el.scrollHeight <= el.clientHeight) loadMore()
  })

  function onScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget
    if (el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_THRESHOLD_PX) {
      loadMore()
    }
  }

  return { items, error, loadingMore, hasMore, containerRef, onScroll, setItems, reload }
}
