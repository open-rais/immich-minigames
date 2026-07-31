// Who'sThatPerson's request/response DTOs - mirrors backend/src/api/dto/whos_that_person.py.

import type { GameType } from "./common"

// Bounding box + image size are in the resolution the face detection ran on, never redacted (needed
// to draw the box regardless of whether the round's been answered) - see backend/src/domain/face.py.
// person_id/person_name/correct are redacted (null) until this round has been answered.
export interface HiddenFaceOut {
  face_id: string
  image_width: number
  image_height: number
  bounding_box_x1: number
  bounding_box_y1: number
  bounding_box_x2: number
  bounding_box_y2: number
  person_id: string | null
  person_name: string | null
  correct: boolean | null
  // Roadmap #10 (rounds review) - what the player guessed, frozen at guess time. guess_person_name
  // is null if that person no longer exists in Immich.
  guess_person_id: string | null
  guess_person_name: string | null
}

export interface WhosThatPersonRoundOut {
  game_type: typeof GameType.WhosThatPerson
  id: string
  round_index: number
  asset_id: string
  faces: HiddenFaceOut[]
  // Whether every hidden face in the round was guessed correctly - null until answered.
  correct: boolean | null
  // Redacted (null) until this round has been answered.
  score_delta: number | null
}

// face_id -> guessed person_id, one entry per hidden face in the round - see
// backend/src/api/dto/whos_that_person.py's WhosThatPersonPlayRoundIn.
export interface WhosThatPersonPlayRoundIn {
  guesses: Record<string, string>
}
