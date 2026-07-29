"""
Roadmap #G (daily games) - generates the shared, pre-computed content every player of a
(challenge_date, game_type, mode) plays that day (see persistence/daily.py's DailyChallengeModel
and docs/TODO/DAILY-GAMES.md §4.3).

Every spec builder below drives a real, throwaway instance of that mode's own game class through
its own `start()`/`create_next_round()` - the exact same picking logic (candidate sampling,
spread/separation, weighted target selection) a normal game already uses - rather than
reimplementing any of it here. Only MoreOrLess and WhosThatPerson/AssetRoundsGame's `has_next_round`
loop shape is replicated (both are guess-independent - see each builder's comment for why that
matters); nothing about *how* an asset/person/round gets picked is duplicated. The throwaway game's
own id/round ids are discarded - only its rounds' *content* (the `EntitySnapshot`/`AssetSnapshot`/
`PersonSnapshot`/`HiddenFace` dataclasses, already `DictCodec`s) is kept, serialized once into
`spec`.
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import DateguessrGame
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import GeoguessrGame
from games.immichdle import ASSET_COUNT_WEIGHT_EXPONENT
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import PersonSnapshot
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import (
    MODE_ALBUM_ASSETS,
    MODE_PERSON_ASSETS,
    AlbumAssetsProvider,
    CandidateProvider,
    MoreOrLessGame,
    PersonAssetsProvider,
)
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import WhosThatPersonGame
from persistence.daily import DailyChallengeModel
from services.daily_settings import DailySettingsService
from services.errors import NotEnoughContentError, UnsupportedGameError
from services.immich_service import ImmichService

# The daily-generator's own throwaway games are never persisted - this owner string just needs to
# be a valid str for BaseGame's constructor, never read back.
_GENERATOR_OWNER = "daily-generator"


class _ExcludingImmichService:
    """Wraps ImmichService to always widen exclude_ids/exclude_asset_ids with a fixed extra set -
    the cross-day no-repeat window (docs/TODO/DAILY-GAMES.md §4.3's "No-repetición"). Only the
    query methods the spec builders below actually call are overridden; everything else (thumbnail
    fetches, person search, ...) is delegated straight through via __getattr__ - this is
    composition, not a subclass, so nothing here depends on ImmichService's own __init__."""

    def __init__(self, inner: ImmichService, extra_exclude_ids: frozenset[UUID]) -> None:
        self._inner = inner
        self._extra_exclude_ids = extra_exclude_ids

    def get_assets(self, *, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any) -> Any:
        return self._inner.get_assets(exclude_ids=exclude_ids | self._extra_exclude_ids, **kwargs)

    def get_persons(self, *, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any) -> Any:
        return self._inner.get_persons(exclude_ids=exclude_ids | self._extra_exclude_ids, **kwargs)

    def get_albums(self, *, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any) -> Any:
        return self._inner.get_albums(exclude_ids=exclude_ids | self._extra_exclude_ids, **kwargs)

    def get_random_asset_with_named_faces(
        self, *, exclude_asset_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        return self._inner.get_random_asset_with_named_faces(
            exclude_asset_ids=exclude_asset_ids | self._extra_exclude_ids, **kwargs
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# -- per-game spec builders --------------------------------------------------------------------


def _build_more_or_less_chain(provider: CandidateProvider, mode: str, chain_length: int) -> dict[str, Any]:
    # MoreOrLessGame.has_next_round() checks the *previous* round's score_delta (a real guess) -
    # meaningless for a precomputed chain, so this drives create_next_round() directly for a fixed
    # length instead (mirroring the real game's own infinite-chain fallback - see
    # games/more_or_less.py's create_next_round, which already tolerates a library smaller than the
    # chain by allowing repeats rather than raising).
    game = MoreOrLessGame.start(id=uuid4(), owner=_GENERATOR_OWNER, mode=mode, provider=provider)
    chain = [game.rounds[0].reference, game.rounds[0].candidate]
    while len(chain) < chain_length + 1:
        next_round = game.create_next_round()
        chain.append(next_round.candidate)
        game.rounds.append(next_round)
    return {"chain": [entity.to_dict() for entity in chain]}


def _build_asset_rounds_spec(
    game_class: type[GeoguessrGame] | type[DateguessrGame], immich_service: Any, settings: dict[str, float]
) -> dict[str, Any]:
    # Unlike MoreOrLess, AssetRoundsGame.has_next_round() never looks at the previous round's guess
    # (see games/asset_rounds.py) - it's already guess-independent, so the real
    # has_next_round()/create_next_round() pair can drive this loop as-is.
    game = game_class.start(id=uuid4(), owner=_GENERATOR_OWNER, immich_service=immich_service, settings=settings)
    total_rounds = game.total_rounds
    while len(game.rounds) < total_rounds:
        if not game.has_next_round():
            raise ValueError(
                f"not enough content to fill {total_rounds} daily rounds for {game_class.game_type}/{game_class.mode}"
            )
        game.rounds.append(game.create_next_round())
    return {
        "rounds": [
            {"main": round_.asset.to_dict(), "extras": [extra.to_dict() for extra in round_.extras]}
            for round_ in game.rounds
        ]
    }


def _build_immichdle_target(immich_service: Any, settings: dict[str, float]) -> dict[str, Any]:
    # No round sequence to precompute (Immichdle's only content is the target - guesses are always
    # free-form), so this replicates ImmichdleGame.start()'s 3-line target selection directly
    # rather than driving a full game instance.
    weight = float(settings.get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
    targets = immich_service.get_persons(named_only=True, randomize=True, limit=1, asset_count_weight=weight)
    if not targets:
        raise ValueError("not enough named people in Immich to generate a daily Immichdle challenge")
    [target_person] = targets
    # Mirrors ImmichdleGame.start()'s has_alternative check - with exactly one named person the
    # normal game refuses to start (the target would be trivially guessable), so the daily must
    # too. Phrased as "at least two named people exist" - equivalent to "someone besides the
    # (named) target exists". When a no-repeat-window wrapper widens this query's exclusions the
    # check can come out stricter than the real game's, but a failure then just triggers
    # get_or_create_challenge's no-exclusion retry, where it's exact.
    if len(immich_service.get_persons(named_only=True, limit=2)) < 2:
        raise ValueError("not enough named people in Immich to generate a daily Immichdle challenge")
    target = PersonSnapshot.of(
        target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
    )
    return {"target": target.to_dict()}


def _build_whos_that_person_spec(immich_service: Any, settings: dict[str, float]) -> dict[str, Any]:
    game = WhosThatPersonGame.start(id=uuid4(), owner=_GENERATOR_OWNER, immich_service=immich_service, settings=settings)
    total_people = game.total_people
    while sum(len(r.faces) for r in game.rounds) < total_people:
        if not game.has_next_round():
            raise ValueError(f"not enough named faces to fill {total_people} daily people for whos-that-person")
        # create_next_round() reads the previous round's ending_streak (normally set by
        # calculate_score() during real play) to seed the next round's incoming_streak - streak is
        # per-player *scoring* state, never part of the shared spec content itself
        # (WhosThatPersonRound.asset_id/faces don't depend on it), so a placeholder unblocks the
        # picking logic without affecting what actually gets picked.
        game.current_round.ending_streak = 0
        game.rounds.append(game.create_next_round())
    return {
        "rounds": [
            {"asset_id": str(round_.asset_id), "faces": [face.to_dict() for face in round_.faces]}
            for round_ in game.rounds
        ]
    }


def _extract_exclusion_ids(game_type: str, spec: dict[str, Any]) -> set[UUID]:
    """Which ids from an already-generated spec should be excluded from a future day's challenge
    of the same (game_type, mode) - only the *answer* content (never decorative extras), see
    docs/TODO/DAILY-GAMES.md §4.3. MoreOrLess is never passed here (decision [F] - no cross-day
    exclusion for it at all)."""
    if game_type in (GEOGUESSR_TYPE, DATEGUESSR_TYPE):
        return {UUID(round_["main"]["id"]) for round_ in spec["rounds"]}
    if game_type == IMMICHDLE_TYPE:
        return {UUID(spec["target"]["id"])}
    if game_type == WHOS_THAT_PERSON_TYPE:
        # Only the shown asset, not the hidden faces' person ids - get_random_asset_with_named_faces
        # only supports excluding assets (see _ExcludingImmichService), and repeating the same
        # asset is what actually gives away/duplicates a round; a person reappearing in a
        # *different* photo is fine.
        return {UUID(round_["asset_id"]) for round_ in spec["rounds"]}
    return set()


class DailyService:
    def __init__(self, session: Session, immich_service: ImmichService) -> None:
        self._session = session
        self._immich_service = immich_service
        self._daily_settings_service = DailySettingsService(session)

    def get_or_create_challenge(self, challenge_date: date, game_type: str, mode: str) -> DailyChallengeModel:
        existing = self._get_challenge(challenge_date, game_type, mode)
        if existing is not None:
            return existing

        # Serializes concurrent first-players of the same (day, game_type, mode): generation is the
        # expensive part (MoreOrLess pays one sampling query per chain link), so instead of two
        # racing requests both generating and one being discarded, the loser blocks here until the
        # winner's commit releases the lock (it's transaction-scoped - the commit below, or the
        # request teardown's rollback on failure, always frees it), then finds the winner's row on
        # the re-SELECT right after. The ON CONFLICT insert below stays as the correctness
        # backstop; this lock is purely about not duplicating the generation work.
        self._session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(f"daily:{challenge_date}:{game_type}:{mode}", 0)))
        )
        existing = self._get_challenge(challenge_date, game_type, mode)
        if existing is not None:
            return existing

        settings = self._daily_settings_service.get_settings(game_type, mode)
        no_repeat_days = int(settings.get("no_repeat_days", 0))
        exclude_ids = self._collect_recent_exclusion_ids(game_type, mode, challenge_date, no_repeat_days)

        try:
            spec = self._build_spec(game_type, mode, settings, exclude_ids)
        except ValueError as exc:
            if not exclude_ids:
                raise NotEnoughContentError(str(exc)) from exc
            # Fallback (§4.3): the exclusion window, not the library itself, may be what's too
            # tight - retry once with no historical exclusion at all.
            try:
                spec = self._build_spec(game_type, mode, settings, frozenset())
            except ValueError as retry_exc:
                raise NotEnoughContentError(str(retry_exc)) from retry_exc

        # INSERT ... ON CONFLICT DO NOTHING + re-SELECT (§4.3's "Carrera") - if two requests race
        # to generate the same day's first challenge, whichever INSERT lands first wins and the
        # loser just reads that row back, no locking needed.
        stmt = (
            pg_insert(DailyChallengeModel)
            .values(
                id=uuid4(), challenge_date=challenge_date, game_type=game_type, mode=mode, spec=spec, settings=settings
            )
            .on_conflict_do_nothing(constraint="uq_daily_challenges_date_type_mode")
        )
        self._session.execute(stmt)
        self._session.commit()

        winner = self._get_challenge(challenge_date, game_type, mode)
        if winner is None:  # either our INSERT or the racing one must have landed
            raise RuntimeError(f"daily challenge for {challenge_date}/{game_type}/{mode} vanished after insert")
        return winner

    def _get_challenge(self, challenge_date: date, game_type: str, mode: str) -> DailyChallengeModel | None:
        return self._session.execute(
            select(DailyChallengeModel).where(
                DailyChallengeModel.challenge_date == challenge_date,
                DailyChallengeModel.game_type == game_type,
                DailyChallengeModel.mode == mode,
            )
        ).scalar_one_or_none()

    def _collect_recent_exclusion_ids(
        self, game_type: str, mode: str, before_date: date, no_repeat_days: int
    ) -> frozenset[UUID]:
        if no_repeat_days <= 0:
            return frozenset()
        cutoff = before_date - timedelta(days=no_repeat_days)
        specs = self._session.execute(
            select(DailyChallengeModel.spec).where(
                DailyChallengeModel.game_type == game_type,
                DailyChallengeModel.mode == mode,
                DailyChallengeModel.challenge_date >= cutoff,
                DailyChallengeModel.challenge_date < before_date,
            )
        ).scalars().all()
        ids: set[UUID] = set()
        for spec in specs:
            ids |= _extract_exclusion_ids(game_type, spec)
        return frozenset(ids)

    def _build_spec(
        self, game_type: str, mode: str, settings: dict[str, float], exclude_ids: frozenset[UUID]
    ) -> dict[str, Any]:
        excluding_service: Any = (
            _ExcludingImmichService(self._immich_service, exclude_ids) if exclude_ids else self._immich_service
        )

        if game_type == MORE_OR_LESS_TYPE:
            provider_cls = PersonAssetsProvider if mode == MODE_PERSON_ASSETS else AlbumAssetsProvider
            # No cross-day exclusion for MoreOrLess (decision [F]) - always the plain service.
            provider = provider_cls(self._immich_service)
            chain_length = int(settings.get("chain_length", 100))
            return _build_more_or_less_chain(provider, mode, chain_length)
        if game_type == GEOGUESSR_TYPE:
            return _build_asset_rounds_spec(GeoguessrGame, excluding_service, settings)
        if game_type == DATEGUESSR_TYPE:
            return _build_asset_rounds_spec(DateguessrGame, excluding_service, settings)
        if game_type == IMMICHDLE_TYPE:
            return _build_immichdle_target(excluding_service, settings)
        if game_type == WHOS_THAT_PERSON_TYPE:
            return _build_whos_that_person_spec(excluding_service, settings)
        raise UnsupportedGameError(f"unsupported daily game/mode: {game_type}/{mode}")
