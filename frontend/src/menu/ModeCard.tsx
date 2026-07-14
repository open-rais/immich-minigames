interface ModeCardProps {
  title: string
  coverUrl?: string
  onClick: () => void
}

// Cover is real per-mode cover art when `coverUrl` is set (mirroring Immich's album cover photos);
// games without art yet (e.g. Immichdle, still a design placeholder) fall back to the plain
// bg-primary color block. No item-count/subtitle line yet either - that'll become the player's
// personal best once user accounts exist, so it's omitted rather than showing anything misleading
// now.
//
// Mirrors Immich's own album card: no visible border/shadow at rest, just the cover + title below
// it; hovering tints the whole card and turns the title into the brand color, matching Immich's
// hover treatment on its album grid. Mobile switches to a full-width row (small square cover on the
// left, title to its right) instead of the stacked desktop card - same breakpoint-driven single
// component tree convention used by MoreOrLessGame.
export function ModeCard({ title, coverUrl, onClick }: ModeCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-4 rounded-2xl p-2 text-left transition-colors hover:bg-hover-tint md:flex-col md:items-stretch md:gap-3 md:p-3 md:border md:border-transparent md:hover:border-line md:hover:shadow-card"
    >
      {coverUrl ? (
        <img
          src={coverUrl}
          alt=""
          className="h-16 w-16 flex-none rounded-lg object-cover md:h-auto md:w-full md:aspect-square md:rounded-xl"
        />
      ) : (
        <div className="h-16 w-16 flex-none rounded-lg bg-primary md:h-auto md:w-full md:aspect-square md:rounded-xl" />
      )}
      <div className="min-w-0 flex-1 md:w-full md:flex-none">
        <div className="truncate font-bold text-ink transition-colors group-hover:text-primary md:text-lg">
          {title}
        </div>
      </div>
    </button>
  )
}
