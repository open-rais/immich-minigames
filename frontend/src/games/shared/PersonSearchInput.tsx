import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { personThumbnailUrl, searchPersons } from "../../api/games"
import type { PersonSearchResultOut } from "../../api/types"
import { PersonAvatar } from "./PersonAvatar"

const DEBOUNCE_MS = 400
const PAGE_SIZE = 5
// Load the next page once the results list is scrolled to within this many px of the bottom.
const SCROLL_THRESHOLD_PX = 48

interface PersonSearchInputProps {
  excludeIds: Set<string>
  // Generic "a person was picked" callback - used both for guessing (Immichdle/WhosThatPerson)
  // and for non-guess selection (the profile page's skin picker, see auth/SkinPicker.tsx).
  onSelect: (personId: string) => void
  disabled: boolean
  // Immichdle-only (see ImmichdleGame.tsx): lets a letter typed anywhere on the page - not just
  // while this input is focused - jump straight into the search, since that screen has nothing
  // else to type into. Left off (default) for WhosThatPerson's popover (one search box per face,
  // ambiguous which one a stray keypress should target) and the profile skin picker (a settings
  // page, not a type-to-search flow).
  focusOnTypeAnywhere?: boolean
}

function isTextEntryElement(el: Element): boolean {
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || (el as HTMLElement).isContentEditable
}

// Debounced search-as-you-type input for picking a person - accent-insensitive, per-token
// word-prefix match against named people (see api/games.ts's searchPersons / backend's
// search_persons), already-picked people filtered out of the results rather than shown disabled
// (excludeIds's callers use it for already-guessed people, but it's just as valid for "don't show
// the current skin again"). Results page in via infinite scroll (see handleResultsScroll) - the
// dropdown's max-height (see the results box className below) only shows VISIBLE_ROWS rows at
// once, so scrolling is the common case even though PAGE_SIZE fetches more than that per page.
export function PersonSearchInput({ excludeIds, onSelect, disabled, focusOnTypeAnywhere = false }: PersonSearchInputProps) {
  const { t } = useTranslation()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<PersonSearchResultOut[]>([])
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
        const { results: found } = await searchPersons(trimmed, { limit: PAGE_SIZE })
        if (requestTokenRef.current !== token) return
        offsetRef.current = found.length
        setHasMore(found.length === PAGE_SIZE)
        setResults(found.filter((p) => !excludeIds.has(p.id)))
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
      const { results: found } = await searchPersons(trimmed, { offset: offsetRef.current, limit: PAGE_SIZE })
      if (requestTokenRef.current !== token) return
      offsetRef.current += found.length
      setHasMore(found.length === PAGE_SIZE)
      setResults((prev) => [...prev, ...found.filter((p) => !excludeIds.has(p.id))])
    } catch {
      if (requestTokenRef.current === token) setHasMore(false)
      advanceAfterLoadRef.current = false
    } finally {
      // Unconditional: loadMore()'s own guard (loadingMore already true) prevents a second call
      // from overlapping this one, so there's never a newer in-flight loadMore whose reset this
      // could clobber - only the debounced search effect's token bump could race here, and if it
      // does, this fetch's result is simply stale (dropped above) while loadingMore still must
      // clear or every future loadMore() call is permanently blocked by its own guard.
      setLoadingMore(false)
    }
  }

  // A page of PAGE_SIZE short rows often doesn't overflow the results box at all, so onScroll
  // alone would never fire to pull in the next page - keep auto-loading right after each fetch
  // until either the box actually has something to scroll or there's nothing left to fetch.
  useEffect(() => {
    const el = resultsBoxRef.current
    if (!el || loading || loadingMore || !hasMore) return
    if (el.scrollHeight <= el.clientHeight) void loadMore()
  })

  // Completes the ArrowDown-past-the-end case: once loadMore() actually appends rows, move the
  // selection onto the first of them (harmless no-op if nothing new landed, e.g. a failed fetch).
  useEffect(() => {
    if (!advanceAfterLoadRef.current) return
    advanceAfterLoadRef.current = false
    setSelectedIndex((current) => Math.min(current + 1, results.length - 1))
  }, [results])

  // Safety net for the rare race where selectedIndex was advanced (e.g. two quick ArrowDown
  // presses) against a results list that then got replaced by a shorter one (a still-in-flight
  // debounced search resolving) - keeps `results[selectedIndex]` always valid or -1.
  useEffect(() => {
    setSelectedIndex((current) => (current >= results.length ? results.length - 1 : current))
  }, [results.length])

  // Keeps the keyboard-selected row visible as it moves in/out of the scrollable results box.
  useEffect(() => {
    if (selectedIndex < 0) return
    resultsBoxRef.current?.querySelector(`[data-index="${selectedIndex}"]`)?.scrollIntoView({ block: "nearest" })
  }, [selectedIndex])

  // focusOnTypeAnywhere: a letter typed while focus is elsewhere on the page (but not inside some
  // other genuine text field) jumps into this search instead of being silently dropped. Manually
  // appends the character and preventDefault()s rather than relying on the browser's normal
  // "focus then let the keystroke land" order, since focusing the input here happens *in response
  // to* this same keydown - the character hasn't been typed into anything yet.
  useEffect(() => {
    if (!focusOnTypeAnywhere || disabled) return
    function handleGlobalKeyDown(e: KeyboardEvent) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return
      if (!/^\p{L}$/u.test(e.key)) return
      const active = document.activeElement
      if (active === inputRef.current || (active instanceof Element && isTextEntryElement(active))) return
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
        setSelectedIndex(0) // wrap back to the top
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setSelectedIndex(selectedIndex <= 0 ? results.length - 1 : selectedIndex - 1) // wrap to the bottom
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (selectedIndex < 0) {
        // First Enter only selects the top result - a second Enter is needed to actually pick it,
        // per the requested "select, then press again to confirm" keyboard flow.
        setSelectedIndex(0)
      } else {
        pick(results[selectedIndex].id)
      }
    }
  }

  function pick(personId: string) {
    onSelect(personId)
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
        // eslint-disable-next-line jsx-a11y/no-autofocus -- deliberate: this input is the sole
        // purpose of both Immichdle's guess bar and Who'sThatPerson's per-face popover (which
        // mounts fresh every time a face box is clicked), so a ready-to-type cursor on open is the
        // expected behavior, not a startle-the-user autofocus anti-pattern.
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={handleInputKeyDown}
        placeholder={t("immichdle.searchPlaceholder")}
        role="combobox"
        aria-expanded={open && results.length > 0}
        aria-controls="person-search-results"
        className="w-full rounded-full border border-line-soft bg-surface py-3 pr-5 pl-11 text-base font-semibold text-ink shadow-card outline-none placeholder:text-faint focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
      />

      {open && query.trim() && (
        // max-h + overflow-y-auto (not overflow-hidden) - the input above always stays put and
        // fully visible; only this results list itself scrolls once there are more matches than
        // fit, same as any standard autocomplete dropdown. The max-h values below cap the box at
        // roughly 3 rows tall (row height = avatar size + py-2.5 padding, which differs at the
        // md breakpoint since PersonAvatar's avatar grows from h-10 to h-14 there) so any further
        // matches require scrolling rather than growing the dropdown indefinitely.
        <div
          ref={resultsBoxRef}
          onScroll={handleResultsScroll}
          id="person-search-results"
          role="listbox"
          className="absolute top-full z-40 mt-2 max-h-[180px] w-full overflow-y-auto overscroll-contain rounded-2xl border border-line bg-surface shadow-card md:max-h-[228px]"
        >
          {loading ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.searching")}</p>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.noResults")}</p>
          ) : (
            <>
              {results.map((person, index) => (
                <button
                  key={person.id}
                  type="button"
                  data-index={index}
                  role="option"
                  aria-selected={index === selectedIndex}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(person.id)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-hover-tint ${
                    index === selectedIndex ? "bg-hover-tint" : ""
                  }`}
                >
                  <PersonAvatar src={personThumbnailUrl(person.id)} alt={person.name} />
                  <span className="truncate font-semibold text-ink">{person.name}</span>
                </button>
              ))}
              {loadingMore && <p className="px-4 py-2 text-sm text-muted">{t("immichdle.searching")}</p>}
            </>
          )}
        </div>
      )}
    </div>
  )
}
