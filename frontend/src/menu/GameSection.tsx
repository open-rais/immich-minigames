import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import type { CatalogGame } from "../games/catalog"
import { ModeCard } from "./ModeCard"

// One collapsible group per game, mirroring Immich's Albums-by-year sections: a chevron + title +
// "(N modes)" header (Immich: "2025 (2 Albums)"), a divider, then a grid of mode cards - collapsing
// the group hides the grid without unmounting it from the route.
export function GameSection({ game }: { game: CatalogGame }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(true)

  return (
    <section>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="mb-1 flex items-center gap-2 text-left"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`flex-none text-ink transition-transform duration-300 ease-out ${expanded ? "" : "-rotate-90"}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
        <h2 className="text-3xl font-bold text-ink md:text-4xl">{t(game.gameTitleKey)}</h2>
        <span className="text-lg text-muted md:text-xl">
          ({t("mainMenu.modesCount", { count: game.modes.length })})
        </span>
      </button>
      <hr className="mb-6 border-line" />

      {/* Grid-rows trick: animates from 0fr to 1fr instead of a hardcoded max-height, so it works
          smoothly no matter how tall the mode grid ends up being. */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <div className="overflow-hidden">
          <div className="grid grid-cols-1 gap-2 pb-1 md:grid-cols-3 md:gap-4 lg:grid-cols-4 xl:grid-cols-5">
            {game.modes.map((mode) => (
              <ModeCard
                key={mode.mode}
                title={t(mode.modeTitleKey)}
                onClick={() => navigate(`/${game.gameType}/${mode.mode}`)}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
