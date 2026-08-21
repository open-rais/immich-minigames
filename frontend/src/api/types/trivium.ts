// Trivium's request/response DTOs - mirrors backend/src/api/dto/trivium.py.

import type { GameType } from "./common"

export type TriviumMediaKind = "none" | "asset" | "person_thumbnail" | "person_thumbnails"

export interface TriviumMediaOut {
  kind: TriviumMediaKind
  asset_id: string | null
  person_id: string | null
  person_ids: string[] | null
}

export interface TriviumRoundOut {
  game_type: typeof GameType.Trivium
  id: string
  round_index: number
  question_kind: string
  // Render data for the question (e.g. { person_id, person_name } for "birthday_year") - never a
  // pre-built phrase, since the app is translated ES/EN/FR/DE: the frontend builds the actual
  // sentence from question_kind + these. Shape depends on question_kind, hence the loose type -
  // narrow it alongside a question_kind check (see games/Trivium/TriviumGame.tsx).
  params: Record<string, unknown>
  alternatives: unknown[]
  media: TriviumMediaOut
  // Redacted (null) until this round has been answered - otherwise the correct answer could be
  // read straight out of the response before guessing.
  correct_index: number | null
  guess: number | null
  elapsed_ms: number | null
  correct: boolean | null
}

// Render data for the one question_kind implemented so far - narrow TriviumRoundOut.params
// against this once question_kind === "birthday_year" is confirmed.
export interface BirthdayYearParams {
  person_id: string
  person_name: string
}

// No game_type here (unlike RoundOut) - game_id already fixes a round's game/mode server-side, so
// the guess body only needs the guess itself.
export interface TriviumPlayRoundIn {
  // Null on a timeout - the frontend must still POST something when the timer runs out, just with
  // no chosen alternative.
  alternative: number | null
  elapsed_ms: number
}
