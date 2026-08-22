"""Immichdle's request/response DTOs - see api/dto/__init__.py. Both modes carry a `mode` field
(not just `game_type`) - api/dto/common.py's RoundOut union needs it to disambiguate the two
Immichdle round shapes, which otherwise share the same game_type literal (see that module's
Discriminator)."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_ALBUM, MODE_PERSON, AlbumdleRound, AlbumSnapshot, PersondleRound, PersonSnapshot


class ImmichdleCluesOut(BaseModel):
    age: Literal["older", "younger", "same", "unknown"]
    asset_count: Literal["more", "less", "equal"]
    first_appearance: Literal["before", "after", "same", "unknown"]
    common_names: int
    ml_similarity: float | None
    assets_together: int
    age_close: bool | None
    first_appearance_close: bool | None
    asset_count_close: bool | None
    age_both_unknown: bool
    first_appearance_both_unknown: bool


class ImmichdleRoundOut(BaseModel):
    game_type: Literal["immichdle"] = IMMICHDLE_TYPE
    mode: Literal["person"] = MODE_PERSON
    id: UUID
    round_index: int
    # Redacted (null) until this round has been answered - same rationale as
    # MoreOrLessRoundOut.candidate_value. The target itself is never in a round's output at
    # all - see GameOut.reveal/PersondleRevealOut below.
    guess_person_id: UUID | None
    guess_person_name: str | None
    guess_asset_count: int | None
    guess_birth_date: date | None
    guess_first_asset_date: date | None
    correct: bool | None
    clues: ImmichdleCluesOut | None

    @classmethod
    def from_round(cls, round_: PersondleRound) -> "ImmichdleRoundOut":
        answered = round_.answered
        guessed = round_.guessed_person if answered else None
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            guess_person_id=guessed.id if guessed else None,
            guess_person_name=guessed.name if guessed else None,
            guess_asset_count=guessed.asset_count if guessed else None,
            guess_birth_date=guessed.birth_date if guessed else None,
            guess_first_asset_date=guessed.first_asset_date if guessed else None,
            correct=round_.correct,
            clues=ImmichdleCluesOut(**round_.clues.to_dict()) if round_.clues else None,
        )


class ImmichdlePlayRoundIn(BaseModel):
    person_id: UUID

    def to_domain(self) -> UUID:
        return self.person_id


class PersondleRevealOut(BaseModel):
    """The mystery person, revealed once a Persondle game is finished - see api/dto/common.py's
    GameOut.reveal/_REVEAL_BUILDERS. Redacted (absent) for every other game/mode and for a
    Persondle game still in progress, where revealing it would be a straight cheat."""

    person_id: UUID
    person_name: str
    asset_count: int
    birth_date: date | None
    first_asset_date: date | None

    @classmethod
    def from_target(cls, target: PersonSnapshot) -> "PersondleRevealOut":
        return cls(
            person_id=target.id,
            person_name=target.name,
            asset_count=target.asset_count,
            birth_date=target.birth_date,
            first_asset_date=target.first_asset_date,
        )


class AlbumdleCluesOut(BaseModel):
    first_asset_date: Literal["before", "after", "same", "unknown"]
    first_asset_date_close: bool | None
    first_asset_date_both_unknown: bool
    asset_count: Literal["more", "less", "equal"]
    asset_count_close: bool | None
    common_names: int
    similarity: float | None
    unique_face_count: Literal["more", "less", "equal"]
    unique_face_count_close: bool | None
    dominant_face_person_id: UUID | None
    dominant_face_name: str | None
    dominant_face_extra_count: int
    dominant_face_comparison: Literal["match", "close", "miss"] | None


class AlbumdleRoundOut(BaseModel):
    game_type: Literal["immichdle"] = IMMICHDLE_TYPE
    mode: Literal["album"] = MODE_ALBUM
    id: UUID
    round_index: int
    # Redacted (null) until this round has been answered - same rationale as
    # ImmichdleRoundOut's guess_* fields above. The target itself is never in a round's output at
    # all - see GameOut.reveal/AlbumdleRevealOut below.
    guess_album_id: UUID | None
    guess_album_name: str | None
    guess_asset_count: int | None
    guess_first_asset_date: date | None
    # The guess's own unique-named-face count - shown as the unique_face_count clue tile's value,
    # same role as guess_asset_count above.
    guess_unique_face_count: int | None
    correct: bool | None
    clues: AlbumdleCluesOut | None

    @classmethod
    def from_round(cls, round_: AlbumdleRound) -> "AlbumdleRoundOut":
        answered = round_.answered
        guessed = round_.guessed_album if answered else None
        return cls(
            id=round_.id,
            round_index=round_.round_index,
            guess_album_id=guessed.id if guessed else None,
            guess_album_name=guessed.name if guessed else None,
            guess_asset_count=guessed.asset_count if guessed else None,
            guess_first_asset_date=guessed.first_asset_date if guessed else None,
            guess_unique_face_count=guessed.unique_named_person_count if guessed else None,
            correct=round_.correct,
            clues=AlbumdleCluesOut(**round_.clues.to_dict()) if round_.clues else None,
        )


class AlbumdlePlayRoundIn(BaseModel):
    album_id: UUID

    def to_domain(self) -> UUID:
        return self.album_id


class AlbumdleRevealOut(BaseModel):
    """The mystery album, revealed once an Albumdle game is finished - same rationale/redaction
    condition as PersondleRevealOut above, see api/dto/common.py's GameOut.reveal/
    _REVEAL_BUILDERS."""

    album_id: UUID
    album_name: str
    asset_count: int
    first_asset_date: date | None
    dominant_person_id: UUID | None
    dominant_person_name: str | None
    dominant_extra_count: int
    unique_named_person_count: int

    @classmethod
    def from_target(cls, target: AlbumSnapshot) -> "AlbumdleRevealOut":
        return cls(
            album_id=target.id,
            album_name=target.name,
            asset_count=target.asset_count,
            first_asset_date=target.first_asset_date,
            dominant_person_id=target.dominant_person_ids[0] if target.dominant_person_ids else None,
            dominant_person_name=target.dominant_person_name,
            dominant_extra_count=max(0, len(target.dominant_person_ids) - 1),
            unique_named_person_count=target.unique_named_person_count,
        )
