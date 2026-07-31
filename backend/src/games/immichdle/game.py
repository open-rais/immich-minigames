"""
Based on the *dle games (Wordle). A person is secretly chosen as the target. The player guesses
other named people (by id) - each guess reveals comparative clues about how it relates to the
target: Age, AssetCount, FirstAppearance, CommonNames, MLSimilarity, AssetsTogether (see
games/immichdle/clues.py for the comparison logic). Starting score is 100, -5 per wrong guess
(floored at 0). The game ends when a guess is correct (won) or the score hits 0 (lost). See
docs/GAMES/IMMICHDLE.md.

Unlike MoreOrLess/Geoguessr/Dateguessr, the guessed entity isn't picked by the server ahead of
time - it's whichever person_id the player submits - so ImmichdleGame overrides play_round() to
resolve/validate the guess and compute its clues before scoring (see games/immichdle/round.py's
ImmichdleRound.calculate_score docstring for why that split exists).
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

from games.base import BaseGame, PlayRoundResult
from games.immichdle.clues import _compute_clues
from games.immichdle.round import ImmichdleRound, PersonSnapshot
from services.immich import ImmichService
from services.ml_service import MLService

GAME_TYPE = "immichdle"
MODE_PERSON = "person"

# Admin feature - public (no leading underscore) since games/settings_registry.py assembles these
# as defaults for the admin-configurable starting_score/wrong_guess_penalty settings, same
# convention already used by e.g. games/geoguessr/game.py's TOTAL_ROUNDS/MAX_SCORE.
STARTING_SCORE = 100
# Exponent `w` in `peso = c_fotos ^ w` (services/immich/persons.py's get_persons
# asset_count_weight), applied only to the target person's selection at game start
# (ImmichdleGame.start). w=0 makes every named person equally likely regardless of photo count;
# w=1 makes a person with 1000 photos 1000x as likely as one with 1 photo. Default is a mild bias
# towards people with more photos (0.2), not a strong one.
ASSET_COUNT_WEIGHT_EXPONENT = 0.2


class DuplicateGuessError(Exception):
    pass


class InvalidGuessError(Exception):
    pass


class ImmichdleGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        rounds: list[ImmichdleRound],
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        score: int = STARTING_SCORE,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            game_type=GAME_TYPE,
            mode=MODE_PERSON,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        self._immich_service = immich_service
        # Injected by GamesService (see services/games_service.py's _game_kwargs), which is the only
        # game-specific dependency any game currently needs beyond immich_service. Still defaults to
        # self-constructing when omitted - same default-construction pattern ImmichService() itself
        # uses elsewhere (e.g. api/api.py's get_immich_service) - so direct/low-level construction
        # (tests, a one-off script) doesn't have to wire up an MLService just to build a game.
        self._ml_service = ml_service or MLService()

    @property
    def target(self) -> PersonSnapshot:
        # The target is the same for every round of the game (unlike MoreOrLess's chaining
        # reference/candidate) - stored once, on the first round's payload, since GameModel has no
        # game-level payload column of its own (see persistence/games.py).
        return self.rounds[0].target

    @classmethod
    def start(
        cls,
        id: UUID,
        immich_service: ImmichService,
        ml_service: MLService | None = None,
        settings: Mapping[str, float] | None = None,
        target: PersonSnapshot | None = None,
    ) -> "ImmichdleGame":
        # A daily game hands in its pre-generated target (games/immichdle/daily.py's build_spec)
        # instead of sampling one here; guesses stay live either way (play_round below always
        # queries immich_service for whatever the player types), so nothing downstream of this
        # needs to know whether the target came from a live sample or a frozen spec.
        if target is None:
            asset_count_weight = float((settings or {}).get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
            # limit=2 in one call instead of a second get_persons just to check an alternative
            # exists - that second query repeated the full asset_face aggregation for nothing more
            # than an existence check.
            target_people = immich_service.get_persons(
                named_only=True, randomize=True, limit=2, asset_count_weight=asset_count_weight
            )
            if len(target_people) < 2:
                raise ValueError("not enough named people in Immich to start an Immichdle game")
            target_person = target_people[0]

            target = PersonSnapshot.of(
                target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
            )

        first_round = ImmichdleRound(id=uuid4(), game_id=id, round_index=1, target=target)
        starting_score = int((settings or {}).get("starting_score", STARTING_SCORE))
        return cls(
            id=id,
            rounds=[first_round],
            immich_service=immich_service,
            ml_service=ml_service,
            score=starting_score,
            settings=settings,
        )

    def _guessed_person_ids(self) -> frozenset[UUID]:
        return frozenset(round_.guess for round_ in self.rounds if round_.guess is not None)

    def play_round(self, guess: UUID) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")
        if guess in self._guessed_person_ids():
            raise DuplicateGuessError(f"person {guess} was already guessed in this game")

        matches = self._immich_service.get_persons(named_only=True, ids=frozenset({guess}), limit=1)
        if not matches:
            raise InvalidGuessError(f"person {guess} is not a valid named person to guess")
        guessed = matches[0]

        current = self.current_round
        current.guess = guess
        current.guessed_person = PersonSnapshot.of(
            guessed, first_asset_date=self._immich_service.get_person_first_asset_date(guessed.id)
        )
        current.clues = _compute_clues(
            target=current.target,
            guess=current.guessed_person,
            ml_similarity=self._ml_service.face_similarity(current.target.id, guessed.id),
            assets_together=self._immich_service.get_assets_together_count(current.target.id, guessed.id),
        )
        current.shown_entities = [guessed.id]
        current.score_delta = current.calculate_score(self._settings)
        self.score = max(0, self.score + current.score_delta)

        if self.has_next_round():
            self.rounds.append(self.create_next_round())
        else:
            self.finished = True

        return PlayRoundResult(score_delta=current.score_delta, score=self.score, finished=self.finished)

    def has_next_round(self) -> bool:
        if self.current_round.correct:
            return False
        return self.score > 0

    def create_next_round(self) -> ImmichdleRound:
        previous = self.current_round
        return ImmichdleRound(id=uuid4(), game_id=self.id, round_index=previous.round_index + 1, target=self.target)
