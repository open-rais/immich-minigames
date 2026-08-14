import { GAME_RECORDS_KEY, getGameRecords } from "../api/games"
import { useLiveQuery } from "../api/queryCache"
import type { GameRecordsOut } from "../api/types/records"
import { GAME_CATALOG } from "../games/catalog"
import { AppHeader } from "./AppHeader"
import { DailySection } from "./DailySection"
import { GameSection } from "./GameSection"

// Modeled on Immich's own Albums view (grouped by year, collapsible): each game is a collapsible
// group, and each of its modes is a card within that group - same shape Immich uses for
// "year -> albums", just swapping "year" for "game" and "album" for "mode".
export function MainMenu() {
  // Personal-best badge - fetched once here rather than per-ModeCard so N
  // modes don't mean N requests; keyed by "gameType:mode" to match GameSection's lookup.
  // "Show cached now, always ask" - games/shared/useGameSession.ts's
  // markRecordBeaten optimistically updates this same cache entry when a finished game beats the
  // stored best, so a beaten record shows here without waiting for this to remount and revalidate.
  const { state } = useLiveQuery<GameRecordsOut>(GAME_RECORDS_KEY, getGameRecords)
  const recordsOut = state.status === "loading" ? undefined : state.value
  const records = new Map(
    (recordsOut?.records ?? []).map((r) => [`${r.game_type}:${r.mode}`, r.best_score]),
  )

  return (
    <div className="min-h-screen bg-app-bg">
      <AppHeader />
      <div className="flex flex-col gap-10 px-6 py-8 md:px-10 md:py-10">
        <DailySection />
        {GAME_CATALOG.map((game) => (
          <GameSection key={game.gameType} game={game} records={records} />
        ))}
      </div>
    </div>
  )
}
