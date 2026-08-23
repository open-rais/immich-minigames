import type { ReactNode } from "react"

// A [‹] label [›] row. Started as the date navigator hand-rolled inside
// menu/DailyLeaderboardPage.tsx and got extracted once the leaderboard needed the same control
// three times over (game category, mode, and that original date).
//
// The label is `children` rather than a string because callers render different things inside it -
// a plain date, a bold game title, or a "<game> · <mode>" pair with its own separator dot.
export function CycleNav({
  children,
  onPrev,
  onNext,
  prevLabel,
  nextLabel,
  prevDisabled = false,
  nextDisabled = false,
}: {
  children: ReactNode
  onPrev: () => void
  onNext: () => void
  prevLabel: string
  nextLabel: string
  prevDisabled?: boolean
  nextDisabled?: boolean
}) {
  const arrowClass =
    "flex-none rounded-full px-2 py-1 text-xl leading-none text-ink transition-colors hover:bg-hover-tint disabled:opacity-30 disabled:hover:bg-transparent"

  return (
    <div className="flex w-full items-center justify-between gap-1">
      <button
        type="button"
        onClick={() => !prevDisabled && onPrev()}
        disabled={prevDisabled}
        className={arrowClass}
        aria-label={prevLabel}
      >
        ‹
      </button>
      {/* min-w-0 so a long "<game> · <mode>" pair truncates inside the row instead of pushing the
          arrows off a narrow phone screen. */}
      <div className="flex min-w-0 flex-1 justify-center">{children}</div>
      <button
        type="button"
        onClick={() => !nextDisabled && onNext()}
        disabled={nextDisabled}
        className={arrowClass}
        aria-label={nextLabel}
      >
        ›
      </button>
    </div>
  )
}
