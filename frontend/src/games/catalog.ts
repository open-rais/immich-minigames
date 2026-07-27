import type { ComponentType } from "react"

import type { GameOut } from "../api/types"
import { GameType, Mode } from "../api/types"
import { DateguessrGame } from "./Dateguessr/DateguessrGame"
import { DateguessrRounds } from "./Dateguessr/DateguessrRounds"
import { GeoguessrGame } from "./Geoguessr/GeoguessrGame"
import { GeoguessrRounds } from "./Geoguessr/GeoguessrRounds"
import { ImmichdleGame } from "./Immichdle/ImmichdleGame"
import { MoreOrLessGame } from "./MoreOrLess/MoreOrLessGame"
import { MoreOrLessRounds } from "./MoreOrLess/MoreOrLessRounds"
import { WhosThatPersonGame } from "./WhosThatPerson/WhosThatPersonGame"

// Mirrors backend/src/services/games_service.py's _GAME_CLASSES/_ROUND_CLASSES by hand - same
// manual-sync convention already used for api/types.ts vs schemas.py. Add an entry here whenever a
// new game/mode is wired up on the backend, so it shows up on the main menu.

// Every <Name>Game component takes this same (optional) prop shape - GameRoute passes the
// catalog's coverUrl through so the idle screen can show it, without each game needing to look
// itself up in the catalog.
export interface GameComponentProps {
  coverUrl?: string
  // Roadmap #10 - whether this mode has a roundsComponent registered (see CatalogMode below),
  // resolved once by GameRoute.tsx and threaded down so FinishedScreen can decide whether to show
  // its "Ver rondas" button without any game-tree module importing this catalog file itself (that
  // would cycle back through the *Game.tsx components this file already imports).
  hasRoundsView?: boolean
}

// Roadmap #10 (rounds review) - every <Name>Rounds component takes the finished GameOut it reviews,
// already loaded by RoundsPage.tsx. onBack is only used by the "fullscreen" family below (the
// "list" family's RoundsShell already renders its own back button, so MoreOrLessRounds/
// ImmichdleRounds just ignore it).
export interface RoundsComponentProps {
  game: GameOut
  onBack?: () => void
}

export interface CatalogMode {
  // No `gameType` here - a mode is always reached through its parent CatalogGame (see
  // findCatalogMode / GameSection), so the parent's gameType is used instead of repeating it.
  mode: string
  modeTitleKey: string
  component: ComponentType<GameComponentProps>
  // Cover shown on the mode's card in the main menu and on its idle screen. Optional - ModeCard
  // falls back to the plain bg-primary block and IdleScreen just skips the image if omitted, for
  // any future game/mode added before its art is ready.
  coverUrl?: string
  // Roadmap #10 - which component reviews a finished game of this mode (games/rounds/RoundsPage.tsx).
  // Optional and added phase by phase (ROUNDS-VIEW.md's F1-F4) - GameScreens.tsx's FinishedScreen
  // only shows its "Ver rondas" button once a mode has one registered here.
  roundsComponent?: ComponentType<RoundsComponentProps>
  // Which of ROUNDS-VIEW.md §2's two visual families that roundsComponent belongs to - "list"
  // (default, unset) is a normal scrolling page wrapped in RoundsShell (MoreOrLess, Immichdle);
  // "fullscreen" (Geoguessr/Dateguessr, later WhosThatPerson) skips RoundsShell entirely and lets
  // the component own the whole viewport itself, the same way *Game.tsx already does - RoundsShell
  // is a padded, scrolling, min-h-dvh column, and MapPicker/TimelineRuler are fixed full-viewport
  // components that don't belong inside one (see RoundsPage.tsx).
  roundsLayout?: "list" | "fullscreen"
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
        roundsComponent: MoreOrLessRounds,
      },
      {
        // Same component as personAssets - it reads its mode from the URL and swaps only the data
        // source (albums) and thumbnail endpoint. See MoreOrLessGame's MODE_CONFIG.
        mode: Mode.AlbumAssets,
        modeTitleKey: "moreOrLess.modes.albumAssets",
        component: MoreOrLessGame,
        coverUrl: "/covers/more-or-less-albums.webp",
        roundsComponent: MoreOrLessRounds,
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
        roundsComponent: GeoguessrRounds,
        roundsLayout: "fullscreen",
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
        roundsComponent: DateguessrRounds,
        roundsLayout: "fullscreen",
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
        coverUrl: "/covers/persondle.webp",
      },
    ],
  },
  {
    gameType: GameType.WhosThatPerson,
    gameTitleKey: "whosThatPerson.title",
    modes: [
      {
        mode: Mode.NamedFaces,
        modeTitleKey: "whosThatPerson.modes.namedFaces",
        component: WhosThatPersonGame,
        coverUrl: "/covers/whos-that-person.webp",
      },
    ],
  },
]

export function findCatalogMode(gameType: string, mode: string): CatalogMode | undefined {
  return GAME_CATALOG.find((game) => game.gameType === gameType)?.modes.find((m) => m.mode === mode)
}
