"""Personal-best records DTOs (roadmap point E, see ScoresService.get_personal_records)."""

from pydantic import BaseModel

from services.scores_service import GameRecord


class GameRecordOut(BaseModel):
    game_type: str
    mode: str
    best_score: int

    @classmethod
    def from_record(cls, record: GameRecord) -> "GameRecordOut":
        return cls(game_type=record.game_type, mode=record.mode, best_score=record.best_score)


class GameRecordsOut(BaseModel):
    records: list[GameRecordOut]

    @classmethod
    def from_records(cls, records: list[GameRecord]) -> "GameRecordsOut":
        return cls(records=[GameRecordOut.from_record(r) for r in records])
