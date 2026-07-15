import { useEffect, useState } from "react"

import { getGameRecords } from "../api/games"
import { GAME_CATALOG } from "../games/catalog"
import { AppHeader } from "./AppHeader"
import { GameSection } from "./GameSection"

// Modeled on Immich's own Albums view (grouped by year, collapsible): each game is a collapsible
// group, and each of its modes is a card within that group - same shape Immich uses for
// "year -> albums", just swapping "year" for "game" and "album" for "mode".
export function MainMenu() {
  // Personal-best badge (roadmap point E) - fetched once here rather than per-ModeCard so N
  // modes don't mean N requests; keyed by "gameType:mode" to match GameSection's lookup. Works
  // for anonymous visitors too (see api/games.ts's getGameRecords), so this isn't gated on auth.
  const [records, setRecords] = useState<Map<string, number>>(new Map())

  useEffect(() => {
    getGameRecords()
      .then(({ records }) => {
        setRecords(new Map(records.map((r) => [`${r.game_type}:${r.mode}`, r.best_score])))
      })
      .catch(() => setRecords(new Map()))
  }, [])

  return (
    <div className="min-h-screen bg-app-bg">
      <AppHeader />
      <div className="flex flex-col gap-10 px-6 py-8 md:px-10 md:py-10">
        {GAME_CATALOG.map((game) => (
          <GameSection key={game.gameType} game={game} records={records} />
        ))}
      </div>
    </div>
  )
}
