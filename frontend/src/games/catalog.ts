import type { ComponentType } from "react"

import type { GameOut } from "../api/types"
import { GameType, Mode } from "../api/types"
import { DateguessrGame } from "./Dateguessr/DateguessrGame"
import { DateguessrRounds } from "./Dateguessr/DateguessrRounds"
import { GeoguessrGame } from "./Geoguessr/GeoguessrGame"
import { GeoguessrRounds } from "./Geoguessr/GeoguessrRounds"
import { ImmichdleGame } from "./Immichdle/ImmichdleGame"
import { ImmichdleRounds } from "./Immichdle/ImmichdleRounds"
import { MoreOrLessGame } from "./MoreOrLess/MoreOrLessGame"
import { MoreOrLessRounds } from "./MoreOrLess/MoreOrLessRounds"
import { TimelineGame } from "./Timeline/TimelineGame"
import { TimelineRounds } from "./Timeline/TimelineRounds"
import { WhosThatPersonGame } from "./WhosThatPerson/WhosThatPersonGame"
import { WhosThatPersonRounds } from "./WhosThatPerson/WhosThatPersonRounds"

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
  // Roadmap #G - true when this instance is playing today's daily challenge (resolved by
  // menu/DailyGameRoute.tsx from the /daily/:gameType/:mode route) instead of a normal game.
  // Threaded into useRoundGame's `daily` config - see that hook for what changes.
  daily?: boolean
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
  // Every mode has one today, but stays optional so a future new game/mode can land before its
  // rounds review is built (same reasoning as coverUrl above) - GameScreens.tsx's FinishedScreen
  // only shows its "Ver rondas" button once a mode has one registered here.
  roundsComponent?: ComponentType<RoundsComponentProps>
  // Which of ROUNDS-VIEW.md §2's two visual families that roundsComponent belongs to - "list"
  // (default, unset) is a normal scrolling page wrapped in RoundsShell (MoreOrLess, Immichdle);
  // "fullscreen" (Geoguessr, Dateguessr, Who'sThatPerson) skips RoundsShell entirely and lets the
  // component own the whole viewport itself, the same way *Game.tsx already does - RoundsShell is
  // a padded, scrolling, min-h-dvh column, and MapPicker/TimelineRuler/AssetPhoto are fixed
  // full-viewport components that don't belong inside one (see RoundsPage.tsx).
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
        roundsComponent: ImmichdleRounds,
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
        roundsComponent: WhosThatPersonRounds,
        roundsLayout: "fullscreen",
      },
    ],
  },
  {
    gameType: GameType.Timeline,
    gameTitleKey: "timeline.title",
    modes: [
      {
        mode: Mode.Arcade,
        modeTitleKey: "timeline.modes.arcade",
        component: TimelineGame,
        coverUrl: "/covers/timeline.webp",
        roundsComponent: TimelineRounds,
        roundsLayout: "fullscreen",
      },
    ],
  },
]

export function findCatalogMode(gameType: string, mode: string): CatalogMode | undefined {
  return GAME_CATALOG.find((game) => game.gameType === gameType)?.modes.find((m) => m.mode === mode)
}
