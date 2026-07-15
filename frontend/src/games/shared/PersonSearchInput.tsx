import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"

import { personThumbnailUrl, searchPersons } from "../../api/games"
import type { PersonSearchResultOut } from "../../api/types"
import { PersonAvatar } from "./PersonAvatar"

const DEBOUNCE_MS = 250
const RESULT_LIMIT = 8

interface PersonSearchInputProps {
  excludeIds: Set<string>
  // Generic "a person was picked" callback - used both for guessing (Immichdle/WhosThatPerson)
  // and for non-guess selection (the profile page's skin picker, see auth/SkinPicker.tsx).
  onSelect: (personId: string) => void
  disabled: boolean
}

// Debounced search-as-you-type input for picking a person - word-prefix match against named
// people (see api/games.ts's searchPersons / backend's search_persons), already-picked people
// filtered out of the results rather than shown disabled (excludeIds's callers use it for
// already-guessed people, but it's just as valid for "don't show the current skin again").
export function PersonSearchInput({ excludeIds, onSelect, disabled }: PersonSearchInputProps) {
  const { t } = useTranslation()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<PersonSearchResultOut[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const requestTokenRef = useRef(0)

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setResults([])
      setLoading(false)
      return
    }
    setLoading(true)
    const token = ++requestTokenRef.current
    const timer = setTimeout(async () => {
      try {
        const { results: found } = await searchPersons(trimmed, { limit: RESULT_LIMIT })
        if (requestTokenRef.current !== token) return
        setResults(found.filter((p) => !excludeIds.has(p.id)))
      } catch {
        if (requestTokenRef.current === token) setResults([])
      } finally {
        if (requestTokenRef.current === token) setLoading(false)
      }
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query, excludeIds])

  function pick(personId: string) {
    onSelect(personId)
    setQuery("")
    setResults([])
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
        placeholder={t("immichdle.searchPlaceholder")}
        className="w-full rounded-full border border-line-soft bg-surface py-3 pr-5 pl-11 text-[15px] font-semibold text-ink shadow-card outline-none placeholder:text-faint focus:border-primary disabled:cursor-not-allowed disabled:opacity-60"
      />

      {open && query.trim() && (
        // max-h + overflow-y-auto (not overflow-hidden) - the input above always stays put and
        // fully visible; only this results list itself scrolls once there are more matches than
        // fit, same as any standard autocomplete dropdown.
        <div className="absolute top-full z-40 mt-2 max-h-64 w-full overflow-y-auto overscroll-contain rounded-2xl border border-line bg-surface shadow-card">
          {loading ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.searching")}</p>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted">{t("immichdle.noResults")}</p>
          ) : (
            results.map((person) => (
              <button
                key={person.id}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(person.id)}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-hover-tint"
              >
                <PersonAvatar src={personThumbnailUrl(person.id)} alt={person.name} />
                <span className="truncate font-semibold text-ink">{person.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
