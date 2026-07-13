import type { ComponentType } from "react"

import { MoreOrLessGame } from "./MoreOrLess/MoreOrLessGame"

// Mirrors backend/src/services/games_service.py's _GAME_CLASSES/_ROUND_CLASSES by hand - same
// manual-sync convention already used for api/types.ts vs schemas.py. Add an entry here whenever a
// new game/mode is wired up on the backend, so it shows up on the main menu.

export interface CatalogMode {
  gameType: string
  mode: string
  modeTitleKey: string
  component: ComponentType
}

export interface CatalogGame {
  gameType: string
  gameTitleKey: string
  modes: CatalogMode[]
}

export const GAME_CATALOG: CatalogGame[] = [
  {
    gameType: "more-or-less",
    gameTitleKey: "moreOrLess.title",
    modes: [
      {
        gameType: "more-or-less",
        mode: "personAssets",
        modeTitleKey: "moreOrLess.modes.personAssets",
        component: MoreOrLessGame,
      },
    ],
  },
]

export function findCatalogMode(gameType: string, mode: string): CatalogMode | undefined {
  return GAME_CATALOG.find((game) => game.gameType === gameType)?.modes.find((m) => m.mode === mode)
}
