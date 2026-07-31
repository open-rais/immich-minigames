// Mirrors backend/src/api/dto/common.py - DTOs and glue shared across every game. Everything that
// doesn't spread across every game/mode lives in a sibling module instead (persons.ts, records.ts,
// leaderboard.ts, daily.ts, admin.ts, config.ts, plus one module per game - see api/types/*.ts).

import type { DateguessrPlayRoundIn, DateguessrRoundOut } from "./dateguessr"
import type { GeoguessrPlayRoundIn, GeoguessrRoundOut } from "./geoguessr"
import type { ImmichdlePlayRoundIn, ImmichdleRoundOut } from "./immichdle"
import type { MoreOrLessPlayRoundIn, MoreOrLessRoundOut } from "./moreOrLess"
import type { TimelinePlayRoundIn, TimelineRoundOut } from "./timeline"
import type { WhosThatPersonPlayRoundIn, WhosThatPersonRoundOut } from "./whosThatPerson"

// Canonical game_type / mode identifiers, mirroring the keys of
// backend/src/services/game_registry.py's GAMES. Single source so the
// catalog, the game components and the discriminated-union tags below don't each hardcode the same
// strings.
export const GameType = {
  MoreOrLess: "more-or-less",
  Geoguessr: "geoguessr",
  Dateguessr: "dateguessr",
  Immichdle: "immichdle",
  WhosThatPerson: "whos-that-person",
  Timeline: "timeline",
} as const
export type GameType = (typeof GameType)[keyof typeof GameType]

export const Mode = {
  PersonAssets: "personAssets",
  AlbumAssets: "albumAssets",
  DistanceBetweenGuess: "distanceBetweenGuess",
  DaysToDate: "daysToDate",
  Person: "person",
  NamedFaces: "namedFaces",
  Arcade: "arcade",
} as const
export type Mode = (typeof Mode)[keyof typeof Mode]

export interface CreateGameIn {
  type: string
  mode: string
}

export type RoundOut =
  | MoreOrLessRoundOut
  | GeoguessrRoundOut
  | DateguessrRoundOut
  | ImmichdleRoundOut
  | WhosThatPersonRoundOut
  | TimelineRoundOut

export interface GameOut {
  id: string
  type: string
  mode: string
  score: number
  finished: boolean
  rounds: RoundOut[]
  // Only ever populated for a finished Immichdle game - the mystery person is revealed once the
  // game is over, win or lose. null for every other game/mode and for an in-progress Immichdle game.
  target_person_id?: string | null
  target_person_name?: string | null
  // Roadmap #10 (rounds review) - same redaction condition as target_person_id/name above.
  target_asset_count?: number | null
  target_birth_date?: string | null
  target_first_asset_date?: string | null
  // Admin feature (ADMIN-FEATURE.md point #4) - the live configured total for this game instance
  // (Geoguessr/Dateguessr: total_rounds, WhosThatPerson: total_people), null for every other game.
  // Read instead of hardcoding a display-only mirror of the backend default (see
  // games/shared/useRoundGame.ts's GameState).
  total_rounds?: number | null
  total_people?: number | null
  // Roadmap #G - set only for a daily-challenge game, null for every normal game. Lets the
  // frontend recognize a resumed/loaded game as a daily one after a page reload (see
  // games/shared/useRoundGame.ts).
  daily_challenge_date?: string | null
}

// Roadmap #e - idle-screen "Continuar" lookup. A wrapper (not a bare nullable GameOut/404) so "no
// active game" - the expected result on every idle-screen visit - is never mistaken for an error.
export interface CurrentGameOut {
  game: GameOut | null
}

// The guess bodies share one endpoint (POST /games/{id}/rounds/{roundId}) - see playRound in
// api/games.ts. Which one is valid is fixed by the game's type/mode server-side, not restated here.
export type PlayRoundIn =
  | MoreOrLessPlayRoundIn
  | GeoguessrPlayRoundIn
  | DateguessrPlayRoundIn
  | ImmichdlePlayRoundIn
  | WhosThatPersonPlayRoundIn
  | TimelinePlayRoundIn

export interface PlayRoundOut {
  // Binary-guess concept (MoreOrLess) - null for games with a continuous score (Geoguessr).
  correct: boolean | null
  score_delta: number
  score: number
  finished: boolean
  // The just-answered round, with its answer now revealed.
  answered_round: RoundOut
  next_round: RoundOut | null
}

// Roadmap #e - profile "Ver juegos" modal - mirrors backend/src/api/dto/common.py's
// RecentGameOut/RecentGamesOut. Only ever finished or abandoned games (never a still-active one).
export interface RecentGameOut {
  id: string
  game_type: string
  mode: string
  score: number
  finished: boolean
  abandoned: boolean
  created_at: string
  // Roadmap #G - whether this was a daily-challenge game (see menu/DailySection.tsx).
  is_daily: boolean
}

export interface RecentGamesOut {
  games: RecentGameOut[]
}
