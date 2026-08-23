import type { TFunction } from "i18next"

import { getGame } from "../api/games"
import type { GameOut } from "../api/types/common"
import type { DailyStatusOut } from "../api/types/daily"
import { findCatalogMode, GAME_CATALOG } from "../games/catalog"
import { buildDailyShareAllMessage } from "../games/shared/dailyShareText"

interface ShareAllEntry {
  gameTitle: string
  modeTitle: string
  game: GameOut
}

// The combined "share every daily result" text, built by both the menu's own share button
// (menu/DailySection.tsx) and the modal that pops up after finishing the last daily of the day
// (menu/DailyFollowUpModal.tsx). Fetches each mode's full GameOut (only that has the rounds the
// share text is drawn from) on demand rather than keeping them all loaded just in case.
//
// Modes with no game_id are skipped - a mode nobody has played has nothing to report. Callers
// decide what to do with a rejection; both of today's treat it as best-effort and stay silent.
export async function buildShareAllText(
  t: TFunction,
  status: DailyStatusOut,
  link: string,
): Promise<string> {
  const entries = await Promise.all(
    status.modes.map(async (modeStatus): Promise<ShareAllEntry | null> => {
      if (!modeStatus.game_id) return null
      const catalogGame = GAME_CATALOG.find((g) => g.gameType === modeStatus.game_type)
      const catalogMode = findCatalogMode(modeStatus.game_type, modeStatus.mode)
      const game = await getGame(modeStatus.game_id)
      return {
        gameTitle: catalogGame ? t(catalogGame.gameTitleKey) : modeStatus.game_type,
        modeTitle: catalogMode ? t(catalogMode.modeTitleKey) : modeStatus.mode,
        game,
      }
    }),
  )
  return buildDailyShareAllMessage(
    t,
    entries.filter((e): e is ShareAllEntry => e !== null),
    link,
  )
}

// Every share link points at the app root: the day's results span several modes, so there's no
// single game route to send someone to.
export function dailyShareLink(): string {
  return `${window.location.origin}/`
}
