"""
Albumdle (roadmap #14) - Immichdle's second mode. An album is secretly chosen as the target. The
player guesses other albums (by id, searched by name) - each guess reveals comparative clues about
how it relates to the target: FirstAssetDate, AssetCount, CommonNames, Similarity (averaged CLIP
embedding, see services/ml_service.py's album_similarity), UniqueFaceCount (distinct named people
across the album's assets), and DominantFace (the named person appearing in the most of the
album's assets - see _pick_dominant_persons/_compare_dominant_face below for the tie-break and
guess-relative-to-target comparison rules). Starting score is 100, -5 per wrong guess (floored at
0, see games/immichdle/game.py's shared STARTING_SCORE/WRONG_GUESS_PENALTY). The game ends when a
guess is correct (won) or the score hits 0 (lost). See docs/GAMES/IMMICHDLE.md.

Target selection is asset-count-weighted, same admin-configurable exponent mechanism as
persondle's (see ASSET_COUNT_WEIGHT_EXPONENT below and services/immich/persons.py's get_persons
docstring for the Efraimidis-Spirakis technique - services/immich/albums.py's get_albums applies
the identical technique over albums).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4

from domain.album import Album
from games.immichdle.game import (
    MODE_ALBUM,
    STARTING_SCORE,
    BaseImmichdleGame,
    BaseImmichdleRound,
    InvalidGuessError,
    is_close,
)
from games.shared.serialization import DictCodec
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService

# Floor applied whenever a target is sampled (start()/build_spec()) so an assetless album (every
# clue would degenerate to "unknown"/0/no dominant face) can never be picked - not an admin
# setting, since there's no reason an admin would ever want to lower it.
_MIN_TARGET_ASSET_COUNT = 1

# Exponent `w` in `peso = c_fotos ^ w` (services/immich/albums.py's get_albums asset_count_weight),
# applied only to the target album's selection at game start (AlbumdleGame.start). w=0 makes every
# album equally likely regardless of asset count; w=1 makes an album with 1000 assets 1000x as
# likely as one with 1. Same default as persondle's (mild bias towards larger albums).
ASSET_COUNT_WEIGHT_EXPONENT = 0.2

CountComparison = Literal["more", "less", "equal"]
DateComparison = Literal["before", "after", "same", "unknown"]
DominantFaceComparison = Literal["match", "close", "miss"]


@dataclass(frozen=True)
class AlbumSnapshot:
    """An album's identifying data frozen at the moment it's looked up (target at game start,
    guess at guess time) - same rationale as persondle.py's PersonSnapshot. Not a DictCodec: the
    shared codec only infers plain UUID/date fields, and `dominant_person_ids` is a tuple of
    UUIDs - hand-rolled to_dict/from_dict instead."""

    id: UUID
    name: str
    asset_count: int
    first_asset_date: date | None
    # The full tied set for "named person appearing in the most assets" (see
    # _pick_dominant_persons) - index 0 is the shown representative (highest global asset_count,
    # then name), the rest exist only so dominant_face_comparison can check the whole set, not just
    # the one shown. Empty when the album has no named face at all.
    dominant_person_ids: tuple[UUID, ...]
    dominant_person_name: str | None
    unique_named_person_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "asset_count": self.asset_count,
            "first_asset_date": self.first_asset_date.isoformat() if self.first_asset_date else None,
            "dominant_person_ids": [str(person_id) for person_id in self.dominant_person_ids],
            "dominant_person_name": self.dominant_person_name,
            "unique_named_person_count": self.unique_named_person_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AlbumSnapshot":
        return cls(
            id=UUID(data["id"]),
            name=data["name"],
            asset_count=data["asset_count"],
            first_asset_date=date.fromisoformat(data["first_asset_date"]) if data["first_asset_date"] else None,
            dominant_person_ids=tuple(UUID(person_id) for person_id in data["dominant_person_ids"]),
            dominant_person_name=data["dominant_person_name"],
            unique_named_person_count=data["unique_named_person_count"],
        )


@dataclass(frozen=True)
class AlbumClues(DictCodec):
    first_asset_date: DateComparison
    first_asset_date_close: bool | None
    first_asset_date_both_unknown: bool
    asset_count: CountComparison
    asset_count_close: bool | None
    common_names: int
    similarity: float | None
    unique_face_count: CountComparison
    unique_face_count_close: bool | None
    # The GUESS's own dominant face (not the target's - that stays secret until the game ends,
    # same redaction rule every other Immichdle clue follows) - the frontend renders this
    # regardless of dominant_face_comparison, same as guess_birth_date is shown alongside the age
    # clue in persondle. UUID | None is one of DictCodec's inferred types, so this needs no
    # hand-written codec (unlike AlbumSnapshot's dominant_person_ids tuple, above).
    dominant_face_person_id: UUID | None
    dominant_face_name: str | None
    dominant_face_extra_count: int
    # None only when the GUESS has no named face at all - distinct from "has one, but it's absent
    # from the target" (miss).
    dominant_face_comparison: DominantFaceComparison | None


def _pick_dominant_persons(
    counts: list[tuple[UUID, str, int]], immich_service: ContentQueries
) -> list[tuple[UUID, str]]:
    """The named person(s) appearing in the most of an album's assets (roadmap #14's "cara que más
    se repite"). `counts` is already ordered by distinct_asset_count desc (see
    services/immich/albums.py's get_album_named_face_counts) - ties (more than one person at the
    max count) are broken by each tied person's *global* asset_count (their total tagged-photo
    count across the whole library, not just this album) descending, then name ascending. Returns
    every tied person (not just the shown representative) - callers use the full set for the
    guess-relative-to-target comparison (see _compare_dominant_face), not just index 0."""
    if not counts:
        return []
    max_count = counts[0][2]
    tied = [(person_id, name) for person_id, name, count in counts if count == max_count]
    if len(tied) == 1:
        return tied
    tied_ids = frozenset(person_id for person_id, _ in tied)
    global_asset_counts = {
        person.id: person.asset_count
        for person in immich_service.get_persons(named_only=True, ids=tied_ids, limit=len(tied))
    }
    return sorted(tied, key=lambda pair: (-global_asset_counts.get(pair[0], 0), pair[1].lower()))


def _compare_dominant_face(
    immich_service: ContentQueries, target: AlbumSnapshot, guess: AlbumSnapshot
) -> DominantFaceComparison | None:
    """Guess-relative-to-target (same convention as every other Immichdle clue): the GUESS's
    dominant person/tied-set is checked against the TARGET's assets. None if the guess has no
    named face at all; "match" if the guess's tied set overlaps the target's own dominant tied set
    (no query needed - both are already frozen snapshots); else "close"/"miss" depending on
    whether any of the guess's tied people appear anywhere in the target's eligible assets at
    all (a live membership check against the still-secret target, mirroring how MLSimilarity/
    AssetsTogether also need a live query against the target in persondle)."""
    if not guess.dominant_person_ids:
        return None
    if set(guess.dominant_person_ids) & set(target.dominant_person_ids):
        return "match"
    present = immich_service.get_persons_present_in_album(target.id, frozenset(guess.dominant_person_ids))
    return "close" if present else "miss"


def _compute_album_clues(
    target: AlbumSnapshot,
    guess: AlbumSnapshot,
    similarity: float | None,
    dominant_face_comparison: DominantFaceComparison | None,
) -> AlbumClues:
    """Every comparison is guess-relative-to-target, mirroring persondle's _compute_person_clues
    exactly - similarity and dominant_face_comparison are precomputed by the caller (both need a
    live query against the target), same reason persondle's ml_similarity/assets_together are
    passed in rather than queried here."""
    if target.first_asset_date is None or guess.first_asset_date is None:
        first_asset_date: DateComparison = "unknown"
    elif guess.first_asset_date < target.first_asset_date:
        first_asset_date = "before"
    elif guess.first_asset_date > target.first_asset_date:
        first_asset_date = "after"
    else:
        first_asset_date = "same"

    if guess.asset_count > target.asset_count:
        asset_count: CountComparison = "more"
    elif guess.asset_count < target.asset_count:
        asset_count = "less"
    else:
        asset_count = "equal"

    if guess.unique_named_person_count > target.unique_named_person_count:
        unique_face_count: CountComparison = "more"
    elif guess.unique_named_person_count < target.unique_named_person_count:
        unique_face_count = "less"
    else:
        unique_face_count = "equal"

    common_names = len(set(target.name.lower().split()) & set(guess.name.lower().split()))

    asset_count_close = None if asset_count == "equal" else abs(guess.asset_count - target.asset_count) < 100
    unique_face_count_close = (
        None
        if unique_face_count == "equal"
        else abs(guess.unique_named_person_count - target.unique_named_person_count) < 5
    )

    return AlbumClues(
        first_asset_date=first_asset_date,
        first_asset_date_close=(
            is_close(target.first_asset_date, guess.first_asset_date)
            if first_asset_date in ("before", "after")
            else None
        ),
        first_asset_date_both_unknown=target.first_asset_date is None and guess.first_asset_date is None,
        asset_count=asset_count,
        asset_count_close=asset_count_close,
        common_names=common_names,
        similarity=similarity,
        unique_face_count=unique_face_count,
        unique_face_count_close=unique_face_count_close,
        dominant_face_person_id=guess.dominant_person_ids[0] if guess.dominant_person_ids else None,
        dominant_face_name=guess.dominant_person_name,
        dominant_face_extra_count=max(0, len(guess.dominant_person_ids) - 1),
        dominant_face_comparison=dominant_face_comparison,
    )


def _snapshot_album(immich_service: ContentQueries, album: Album) -> AlbumSnapshot:
    """Composes the album queries into one frozen AlbumSnapshot - shared by start()/build_spec()
    (for the target) and _resolve_and_score_guess() (for a guess)."""
    first_asset_date = immich_service.get_album_first_asset_date(album.id)
    counts = immich_service.get_album_named_face_counts(album.id)
    dominant = _pick_dominant_persons(counts, immich_service)
    return AlbumSnapshot(
        id=album.id,
        name=album.name,
        asset_count=album.asset_count,
        first_asset_date=first_asset_date,
        dominant_person_ids=tuple(person_id for person_id, _ in dominant),
        dominant_person_name=dominant[0][1] if dominant else None,
        unique_named_person_count=len(counts),
    )


class AlbumdleRound(BaseImmichdleRound):
    def __init__(self, id: UUID, game_id: UUID, round_index: int, target: AlbumSnapshot) -> None:
        super().__init__(id, game_id, round_index, target)
        self.guessed_album: AlbumSnapshot | None = None
        self.clues: AlbumClues | None = None

    @property
    def guessed_entity_id(self) -> UUID | None:
        return self.guessed_album.id if self.guessed_album else None

    def apply_guess(self, guessed: AlbumSnapshot, clues: AlbumClues) -> None:
        self.guessed_album = guessed
        self.clues = clues
        self.shown_entities = [guessed.id]

    def to_payload(self) -> dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "guess": str(self.guess) if self.guess else None,
            "guessed_album": self.guessed_album.to_dict() if self.guessed_album else None,
            "clues": self.clues.to_dict() if self.clues else None,
        }

    @classmethod
    def from_payload(
        cls, id: UUID, game_id: UUID, round_index: int, payload: dict[str, Any], score_delta: int | None
    ) -> "AlbumdleRound":
        round_ = cls(
            id=id, game_id=game_id, round_index=round_index, target=AlbumSnapshot.from_dict(payload["target"])
        )
        round_.guess = UUID(payload["guess"]) if payload["guess"] else None
        round_.guessed_album = (
            AlbumSnapshot.from_dict(payload["guessed_album"]) if payload["guessed_album"] else None
        )
        round_.clues = AlbumClues.from_dict(payload["clues"]) if payload["clues"] else None
        round_.score_delta = score_delta
        if round_.guessed_album is not None:
            round_.shown_entities = [round_.guessed_album.id]
        return round_


class AlbumdleGame(BaseImmichdleGame):
    def __init__(
        self,
        id: UUID,
        rounds: list[AlbumdleRound],
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        score: int = STARTING_SCORE,
        finished: bool = False,
        settings: dict[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            mode=MODE_ALBUM,
            rounds=rounds,
            immich_service=immich_service,
            ml_service=ml_service,
            score=score,
            finished=finished,
            settings=settings,
        )

    @classmethod
    def start(
        cls,
        id: UUID,
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        settings: dict[str, float] | None = None,
        target: AlbumSnapshot | None = None,
    ) -> "AlbumdleGame":
        # A daily game hands in its pre-generated target (build_spec below) instead of sampling
        # one here - same pattern as PersondleGame.start(), including the asset-count weighting.
        if target is None:
            asset_count_weight = float((settings or {}).get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
            # limit=2 in one call instead of a second get_albums just to check an alternative
            # exists - same reasoning as PersondleGame.start()'s identical trick.
            target_albums = immich_service.get_albums(
                randomize=True,
                limit=2,
                min_asset_count=_MIN_TARGET_ASSET_COUNT,
                asset_count_weight=asset_count_weight,
            )
            if len(target_albums) < 2:
                raise ValueError("not enough albums in Immich to start an Albumdle game")
            target = _snapshot_album(immich_service, target_albums[0])

        first_round = AlbumdleRound(id=uuid4(), game_id=id, round_index=1, target=target)
        starting_score = int((settings or {}).get("starting_score", STARTING_SCORE))
        return cls(
            id=id,
            rounds=[first_round],
            immich_service=immich_service,
            ml_service=ml_service,
            score=starting_score,
            settings=settings,
        )

    def _resolve_and_score_guess(self, guess: UUID) -> tuple[AlbumSnapshot, AlbumClues]:
        matches = self._immich_service.get_albums(ids=frozenset({guess}), limit=1)
        if not matches:
            raise InvalidGuessError(f"album {guess} is not a valid album to guess")
        guessed = _snapshot_album(self._immich_service, matches[0])
        dominant_comparison = _compare_dominant_face(self._immich_service, self.target, guessed)
        similarity = self._ml_service.album_similarity(self.target.id, guessed.id)
        clues = _compute_album_clues(self.target, guessed, similarity, dominant_comparison)
        return guessed, clues

    def create_next_round(self) -> AlbumdleRound:
        previous = self.current_round
        return AlbumdleRound(id=uuid4(), game_id=self.id, round_index=previous.round_index + 1, target=self.target)


def build_spec(immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    # Replicates AlbumdleGame.start()'s target-selection directly rather than driving a full game
    # instance, since there's no round sequence to precompute (same shape as persondle's
    # build_spec).
    weight = float(settings.get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
    targets = immich_service.get_albums(
        randomize=True, limit=1, min_asset_count=_MIN_TARGET_ASSET_COUNT, asset_count_weight=weight
    )
    if not targets:
        raise ValueError("not enough albums in Immich to generate a daily Albumdle challenge")
    [target_album] = targets
    # Mirrors AlbumdleGame.start()'s has_alternative check.
    if len(immich_service.get_albums(min_asset_count=_MIN_TARGET_ASSET_COUNT, limit=2)) < 2:
        raise ValueError("not enough albums in Immich to generate a daily Albumdle challenge")
    target = _snapshot_album(immich_service, target_album)
    return {"target": target.to_dict()}


def game_kwargs(
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"immich_service": immich_service, "ml_service": ml_service, "settings": settings}
    # Only the very first round needs the target explicitly - AlbumdleRound.from_payload already
    # carries it for every later reconstruction.
    if rounds_played == 0:
        kwargs["target"] = AlbumSnapshot.from_dict(spec["target"])
    return kwargs
