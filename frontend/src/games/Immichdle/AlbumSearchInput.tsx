import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { albumThumbnailUrl, searchAlbums } from "../../api/games"
import type { AlbumSearchResultOut } from "../../api/types/albums"
import { PersonAvatar } from "../shared/PersonAvatar"

const DEBOUNCE_MS = 400
const PAGE_SIZE = 5
// Load the next page once the results list is scrolled to within this many px of the bottom.
const SCROLL_THRESHOLD_PX = 48

interface AlbumSearchInputProps {
  excludeIds: Set<string>
  onSelect: (albumId: string) => void
  disabled: boolean
  // Lets a letter typed anywhere on the page - not just while this input is focused - jump
  // straight into the search, since Albumdle's play screen has nothing else to type into. Same
  // convention as PersonSearchInput's own prop of the same name.
  focusOnTypeAnywhere?: boolean
}

function isTextEntryElement(el: Element): boolean {
  return (
    el.tagName === "INPUT" || el.tagName === "TEXTAREA" || (el as HTMLElement).isContentEditable
  )
}

// Debounced search-as-you-type input for picking an album - accent-insensitive, per-token
// word-prefix match against album names (see api/games.ts's searchAlbums / backend's
// search_albums). Mirrors games/shared/PersonSearchInput.tsx exactly, substituting albums for
// people (kept local to Immichdle/ rather than promoted to shared/ - nothing else needs an album
// search box today, see games/Immichdle/albumdle.py's module docstring for the mode itself).
export function AlbumSearchInput({
  excludeIds,
  onSelect,
  disabled,
  focusOnTypeAnywhere = false,
}: AlbumSearchInputProps) {
  const { t } = useTranslation()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<AlbumSearchResultOut[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  // -1 = nothing keyboard-selected yet. Index into `results` (the excludeIds-filtered, currently
  // rendered list), not the raw offset - see loadMore's own offsetRef for that distinction.
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const requestTokenRef = useRef(0)
  // Raw fetched-count offset for the next page - tracked separately from results.length since
  // results is filtered by excludeIds and would otherwise cause pages to be skipped/re-fetched.
  const offsetRef = useRef(0)
  const resultsBoxRef = useRef<HTMLDivElement>(null)
  // Set right before an ArrowDown-triggered loadMore() so the effect below can advance the
  // selection to the first newly-loaded row once it lands, instead of leaving it stuck at the
  // old last row while the fetch is in flight.
  const advanceAfterLoadRef = useRef(false)

  useEffect(() => {
    const trimmed = query.trim()
    advanceAfterLoadRef.current = false
    setSelectedIndex(-1)
    if (!trimmed) {
      setResults([])
      setHasMore(false)
      setLoading(false)
      return
    }
    setLoading(true)
    const token = ++requestTokenRef.current
    const timer = setTimeout(async () => {
      try {
        const { results: found } = await searchAlbums(trimmed, { limit: PAGE_SIZE })
        if (requestTokenRef.current !== token) return
        offsetRef.current = found.length
        setHasMore(found.length === PAGE_SIZE)
        setResults(found.filter((a) => !excludeIds.has(a.id)))
      } catch {
        if (requestTokenRef.current === token) {
          setResults([])
          setHasMore(false)
        }
      } finally {
        if (requestTokenRef.current === token) setLoading(false)
      }
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query, excludeIds])

  async function loadMore() {
    const trimmed = query.trim()
    if (!trimmed || loading || loadingMore || !hasMore) return
    setLoadingMore(true)
    const token = requestTokenRef.current
    try {
      const { results: found } = await searchAlbums(trimmed, {
        offset: offsetRef.current,
        limit: PAGE_SIZE,
      })
      if (requestTokenRef.current !== token) return
      offsetRef.current += found.length
      setHasMore(found.length === PAGE_SIZE)
      setResults((prev) => [...prev, ...found.filter((a) => !excludeIds.has(a.id))])
    } catch {
      if (requestTokenRef.current === token) setHasMore(false)
      advanceAfterLoadRef.current = false
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    const el = resultsBoxRef.current
    if (!el || loading || loadingMore || !hasMore) return
    if (el.scrollHeight <= el.clientHeight) void loadMore()
  })

  useEffect(() => {
    if (!advanceAfterLoadRef.current) return
    advanceAfterLoadRef.current = false
    setSelectedIndex((current) => Math.min(current + 1, results.length - 1))
  }, [results])

  useEffect(() => {
    setSelectedIndex((current) => (current >= results.length ? results.length - 1 : current))
  }, [results.length])

  useEffect(() => {
    if (selectedIndex < 0) return
    resultsBoxRef.current
      ?.querySelector(`[data-index="${selectedIndex}"]`)
      ?.scrollIntoView({ block: "nearest" })
  }, [selectedIndex])

  useEffect(() => {
    if (!focusOnTypeAnywhere || disabled) return
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return
      if (!/^\p{L}$/u.test(e.key)) return
      const active = document.activeElement
      if (active === inputRef.current || (active instanceof Element && isTextEntryElement(active)))
        return
      e.preventDefault()
      inputRef.current?.focus()
      setQuery((prev) => prev + e.key)
    }
    document.addEventListener("keydown", handleGlobalKeyDown)
    return () => document.removeEventListener("keydown", handleGlobalKeyDown)
  }, [focusOnTypeAnywhere, disabled])

  function handleResultsScroll(e: React.UIEvent<HTMLDivElement>) {
    const el = e.currentTarget
    if (el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_THRESHOLD_PX) {
      void loadMore()
    }
  }

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return

    if (e.key === "ArrowDown") {
      e.preventDefault()
      if (selectedIndex < 0) {
        setSelectedIndex(0)
      } else if (selectedIndex < results.length - 1) {
        setSelectedIndex(selectedIndex + 1)
      } else if (hasMore) {
        advanceAfterLoadRef.current = true
        void loadMore()
      } else {
        setSelectedIndex(0)
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setSelectedIndex(selectedIndex <= 0 ? results.length - 1 : selectedIndex - 1)
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (selectedIndex < 0) {
        setSelectedIndex(0)
      } else {
        pick(results[selectedIndex].id)
      }
    }
  }

  function pick(albumId: string) {
    onSelect(albumId)
    setQuery("")
    setResults([])
    setHasMore(false)
    setSelectedIndex(-1)
    setOpen(false)
  }

  return (
    <div className="relative w-full">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-faint"
      >
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
      <input
        ref={inputRef}
        type="text"
        value={query}
        disabled={disabled}
        // eslint-disable-next-line jsx-a11y/no-autofocus -- deliberate, same rationale as
        // PersonSearchInput's own autoFocus.
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={handleInputKeyDown}
        placeholder={t("immichdle.album.searchPlaceholder")}
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls="album-search-results"
        className="w-full rounded-full border border-line-soft bg-surface py-3 pr-5 pl-11 text-base font-semibold text-ink shadow-card outline-none placeholder:text-faint focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
      />

      {open && query.trim() && (
        <div
          ref={resultsBoxRef}
          onScroll={handleResultsScroll}
          id="album-search-results"
          role="listbox"
          className="absolute top-full z-40 mt-2 max-h-[180px] w-full overflow-y-auto overscroll-contain rounded-2xl border border-line bg-surface shadow-card md:max-h-[228px]"
        >
          {loading ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.searching")}</p>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.noResults")}</p>
          ) : (
            <>
              {results.map((album, index) => (
                <button
                  key={album.id}
                  type="button"
                  data-index={index}
                  role="option"
                  aria-selected={index === selectedIndex}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(album.id)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-hover-tint ${
                    index === selectedIndex ? "bg-hover-tint" : ""
                  }`}
                >
                  <PersonAvatar src={albumThumbnailUrl(album.id)} alt={album.name} />
                  <span className="truncate font-semibold text-ink">{album.name}</span>
                </button>
              ))}
              {loadingMore && (
                <p className="px-4 py-2 text-sm text-muted">{t("immichdle.searching")}</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
