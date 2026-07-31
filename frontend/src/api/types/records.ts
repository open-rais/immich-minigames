// Roadmap point E - main menu personal-best badge (see menu/ModeCard.tsx) - mirrors backend/src/
// api/dto/records.py.

export interface GameRecordOut {
  game_type: string
  mode: string
  best_score: number
}

export interface GameRecordsOut {
  records: GameRecordOut[]
}
