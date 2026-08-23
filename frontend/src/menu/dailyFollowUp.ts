import type { DailyModeStatusOut, DailyStatusOut } from "../api/types/daily"
import type { CatalogGame, CatalogMode } from "../games/catalog"
import { GAME_CATALOG } from "../games/catalog"

// Which of today's dailies are still open, behind menu/DailyFollowUpModal.tsx (the modal that pops
// up right after a daily is finished). Pure and catalog-injectable for its own unit tests, same
// shape as menu/leaderboardNav.ts.

export interface PendingDaily {
  status: DailyModeStatusOut
  game: CatalogGame
  mode: CatalogMode
}

// "Pending" is anything not finished - a mode started and left mid-game counts, and the modal
// shows it as "Continuar" rather than hiding it (the player would otherwise have to go back to the
// menu to find it again).
//
// Modes that don't resolve in the catalog are dropped: an admin can enable a rotation mode this
// frontend build doesn't know about, and there'd be no title or cover to draw a row with - same
// filter DailySection.tsx applies to its own cards.
export function pendingDailyModes(
  status: DailyStatusOut | undefined,
  catalog: CatalogGame[] = GAME_CATALOG,
): PendingDaily[] {
  const pending: PendingDaily[] = []
  for (const modeStatus of status?.modes ?? []) {
    if (modeStatus.status === "finished") continue
    const game = catalog.find((g) => g.gameType === modeStatus.game_type)
    const mode = game?.modes.find((m) => m.mode === modeStatus.mode)
    if (!game || !mode) continue
    pending.push({ status: modeStatus, game, mode })
  }
  return pending
}
