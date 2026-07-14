import type { ComponentType } from "react"

import { GameType, Mode } from "../api/types"
import { DateguessrGame } from "./Dateguessr/DateguessrGame"
import { GeoguessrGame } from "./Geoguessr/GeoguessrGame"
import { ImmichdleGame } from "./Immichdle/ImmichdleGame"
import { MoreOrLessGame } from "./MoreOrLess/MoreOrLessGame"

// Mirrors backend/src/services/games_service.py's _GAME_CLASSES/_ROUND_CLASSES by hand - same
// manual-sync convention already used for api/types.ts vs schemas.py. Add an entry here whenever a
// new game/mode is wired up on the backend, so it shows up on the main menu.

// Every <Name>Game component takes this same (optional) prop shape - GameRoute passes the
// catalog's coverUrl through so the idle screen can show it, without each game needing to look
// itself up in the catalog.
export interface GameComponentProps {
  coverUrl?: string
}

export interface CatalogMode {
  // No `gameType` here - a mode is always reached through its parent CatalogGame (see
  // findCatalogMode / GameSection), so the parent's gameType is used instead of repeating it.
  mode: string
  modeTitleKey: string
  component: ComponentType<GameComponentProps>
  // Cover shown on the mode's card in the main menu and on its idle screen. Omitted for games
  // without art yet - ModeCard falls back to the plain bg-primary block and IdleScreen just skips
  // the image in that case (e.g. Immichdle, still a placeholder).
  coverUrl?: string
}

export interface CatalogGame {
  gameType: string
  gameTitleKey: string
  modes: CatalogMode[]
}

export const GAME_CATALOG: CatalogGame[] = [
  {
    gameType: GameType.MoreOrLess,
    gameTitleKey: "moreOrLess.title",
    modes: [
      {
        mode: Mode.PersonAssets,
        modeTitleKey: "moreOrLess.modes.personAssets",
        component: MoreOrLessGame,
        coverUrl: "/covers/more-or-less.webp",
      },
    ],
  },
  {
    gameType: GameType.Geoguessr,
    gameTitleKey: "geoguessr.title",
    modes: [
      {
        mode: Mode.DistanceBetweenGuess,
        modeTitleKey: "geoguessr.modes.distanceBetweenGuess",
        component: GeoguessrGame,
        coverUrl: "/covers/geoguessr.webp",
      },
    ],
  },
  {
    gameType: GameType.Dateguessr,
    gameTitleKey: "dateguessr.title",
    modes: [
      {
        mode: Mode.DaysToDate,
        modeTitleKey: "dateguessr.modes.daysToDate",
        component: DateguessrGame,
        coverUrl: "/covers/dateguessr.webp",
      },
    ],
  },
  {
    gameType: GameType.Immichdle,
    gameTitleKey: "immichdle.title",
    modes: [
      {
        mode: Mode.Person,
        modeTitleKey: "immichdle.modes.person",
        component: ImmichdleGame,
      },
    ],
  },
]

export function findCatalogMode(gameType: string, mode: string): CatalogMode | undefined {
  return GAME_CATALOG.find((game) => game.gameType === gameType)?.modes.find((m) => m.mode === mode)
}
