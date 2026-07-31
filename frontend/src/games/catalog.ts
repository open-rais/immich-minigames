import type { ComponentType } from "react"
import { lazy } from "react"

import type { GameOut } from "../api/types/common"
import { GameType, Mode } from "../api/types/common"

// Every game/rounds component is lazy-loaded - this is what
// keeps maplibre-gl (Geoguessr's map, ~1 MB minified) and the other 5 games out of the initial
// bundle, since this catalog is imported eagerly from the app's entry routes. Callers that render
// `component`/`roundsComponent` need a <Suspense> boundary above them (see menu/GameRoute.tsx,
// menu/DailyGameRoute.tsx, games/rounds/RoundsPage.tsx).
const DateguessrGame = lazy(() =>
  import("./Dateguessr/DateguessrGame").then((m) => ({ default: m.DateguessrGame })),
)
const DateguessrRounds = lazy(() =>
  import("./Dateguessr/DateguessrRounds").then((m) => ({ default: m.DateguessrRounds })),
)
const GeoguessrGame = lazy(() =>
  import("./Geoguessr/GeoguessrGame").then((m) => ({ default: m.GeoguessrGame })),
)
const GeoguessrRounds = lazy(() =>
  import("./Geoguessr/GeoguessrRounds").then((m) => ({ default: m.GeoguessrRounds })),
)
const ImmichdleGame = lazy(() =>
  import("./Immichdle/ImmichdleGame").then((m) => ({ default: m.ImmichdleGame })),
)
const ImmichdleRounds = lazy(() =>
  import("./Immichdle/ImmichdleRounds").then((m) => ({ default: m.ImmichdleRounds })),
)
const MoreOrLessGame = lazy(() =>
  import("./MoreOrLess/MoreOrLessGame").then((m) => ({ default: m.MoreOrLessGame })),
)
const MoreOrLessRounds = lazy(() =>
  import("./MoreOrLess/MoreOrLessRounds").then((m) => ({ default: m.MoreOrLessRounds })),
)
const TimelineGame = lazy(() =>
  import("./Timeline/TimelineGame").then((m) => ({ default: m.TimelineGame })),
)
const TimelineRounds = lazy(() =>
  import("./Timeline/TimelineRounds").then((m) => ({ default: m.TimelineRounds })),
)
const WhosThatPersonGame = lazy(() =>
  import("./WhosThatPerson/WhosThatPersonGame").then((m) => ({ default: m.WhosThatPersonGame })),
)
const WhosThatPersonRounds = lazy(() =>
  import("./WhosThatPerson/WhosThatPersonRounds").then((m) => ({
    default: m.WhosThatPersonRounds,
  })),
)

// Mirrors backend/src/services/game_registry.py's GAMES by hand - same
// manual-sync convention already used for api/types.ts vs api/dto/. Add an entry here whenever a
// new game/mode is wired up on the backend, so it shows up on the main menu.

// Every <Name>Game component takes this same (optional) prop shape - GameRoute passes the
// catalog's coverUrl through so the idle screen can show it, without each game needing to look
// itself up in the catalog.
export interface GameComponentProps {
  coverUrl?: string
  // Whether this mode has a roundsComponent registered (see CatalogMode below),
  // resolved once by GameRoute.tsx and threaded down so FinishedScreen can decide whether to show
  // its "Ver rondas" button without any game-tree module importing this catalog file itself (that
  // would cycle back through the *Game.tsx components this file already imports).
  hasRoundsView?: boolean
  // True when this instance is playing today's daily challenge (resolved by
  // menu/DailyGameRoute.tsx from the /daily/:gameType/:mode route) instead of a normal game.
  // Threaded into useRoundGame's `daily` config - see that hook for what changes.
  daily?: boolean
}

// Every <Name>Rounds component takes the finished GameOut it reviews,
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
  // Which component reviews a finished game of this mode (games/rounds/RoundsPage.tsx).
  // Every mode has one today, but stays optional so a future new game/mode can land before its
  // rounds review is built (same reasoning as coverUrl above) - GameScreens.tsx's FinishedScreen
  // only shows its "Ver rondas" button once a mode has one registered here.
  roundsComponent?: ComponentType<RoundsComponentProps>
  // Which of the two visual families that roundsComponent belongs to - "list"
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
