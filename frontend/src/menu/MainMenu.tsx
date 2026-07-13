import { GAME_CATALOG } from "../games/catalog"
import { AppHeader } from "./AppHeader"
import { GameSection } from "./GameSection"

// Modeled on Immich's own Albums view (grouped by year, collapsible): each game is a collapsible
// group, and each of its modes is a card within that group - same shape Immich uses for
// "year -> albums", just swapping "year" for "game" and "album" for "mode".
export function MainMenu() {
  return (
    <div className="min-h-screen bg-app-bg">
      <AppHeader />
      <div className="flex flex-col gap-10 px-6 py-8 md:px-10 md:py-10">
        {GAME_CATALOG.map((game) => (
          <GameSection key={game.gameType} game={game} />
        ))}
      </div>
    </div>
  )
}
