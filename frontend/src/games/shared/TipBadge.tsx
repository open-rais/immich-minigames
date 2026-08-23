import { useState } from "react"
import { useTranslation } from "react-i18next"

/**
 * The small "did you know" pill on a finished game's screen. Purely informational - the actions it
 * points at (View game / Leaderboards / Share) are already buttons on the same screen - plus an
 * "x" that hides it for the rest of this screen. Nothing is persisted: which tip shows is rolled
 * fresh every time (see tips.ts).
 *
 * Pinned to the bottom of the viewport rather than placed in the finished screen's own centered
 * column, so a game that happens to draw a tip doesn't push its buttons up relative to one that
 * doesn't - the screen must look identical either way.
 */
export function TipBadge({ tipKey }: { tipKey: string }) {
  const { t } = useTranslation()
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <div className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] left-1/2 z-30 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-start gap-3 rounded-2xl bg-badge-bg px-4 py-3 text-left shadow-card">
      <p className="flex-1 text-base leading-6 text-badge-label">{t(tipKey)}</p>
      <button
        type="button"
        aria-label={t("common.tips.dismiss")}
        onClick={() => setDismissed(true)}
        className="-mr-1 mt-0.5 shrink-0 rounded-full p-1 text-badge-label opacity-60 transition hover:bg-badge-bg-hover hover:opacity-100"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        >
          <line x1="6" y1="6" x2="18" y2="18" />
          <line x1="18" y1="6" x2="6" y2="18" />
        </svg>
      </button>
    </div>
  )
}
