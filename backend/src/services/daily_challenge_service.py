"""
Roadmap #G (daily games) - generates the shared, pre-computed content every player of a
(challenge_date, game_type, mode) plays that day (see persistence/daily.py's DailyChallengeModel
and docs/TODO/DAILY-GAMES.md §4.3). Content generation itself is entirely delegated to each game's
own `games/<game>/daily.py::build_spec()` (games/daily.py's DailySupport contract) - this module
owns only what's genuinely generic across every game: the challenge date, the advisory lock, the
race-safe insert, the cross-day exclusion window, and the wrapper (_ExcludingImmichService) that
applies it.

Named DailyChallengeService (not "daily games") because services/daily_games_service.py's
DailyGamesService is a different thing - this one generates the shared challenge content, that one
turns a generated challenge into a specific player's played game.
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from games.registry import GAMES
from persistence.daily import DailyChallengeModel
from services.daily_settings import DailySettingsService
from services.errors import NotEnoughContentError, UnsupportedGameError
from services.immich_service import ImmichService


class _ExcludingImmichService:
    """Wraps ImmichService to always widen exclude_ids/exclude_asset_ids with a fixed extra set -
    the cross-day no-repeat window (docs/TODO/DAILY-GAMES.md §4.3's "No-repetición"). Only the
    query methods any game's build_spec() actually calls are overridden; everything else (thumbnail
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


class DailyChallengeService:
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
        spec_entry = GAMES.get((game_type, mode))
        if spec_entry is None or spec_entry.daily is None:
            return frozenset()
        cutoff = before_date - timedelta(days=no_repeat_days)
        specs = (
            self._session.execute(
                select(DailyChallengeModel.spec).where(
                    DailyChallengeModel.game_type == game_type,
                    DailyChallengeModel.mode == mode,
                    DailyChallengeModel.challenge_date >= cutoff,
                    DailyChallengeModel.challenge_date < before_date,
                )
            )
            .scalars()
            .all()
        )
        ids: set[UUID] = set()
        for spec in specs:
            # decision [F] (docs/TODO/DAILY-GAMES.md) - MoreOrLess's exclusion_ids() always returns
            # set(), so this naturally stays empty for it without any game-type special case here.
            ids |= spec_entry.daily.exclusion_ids(spec)
        return frozenset(ids)

    def _build_spec(
        self, game_type: str, mode: str, settings: dict[str, float], exclude_ids: frozenset[UUID]
    ) -> dict[str, Any]:
        spec_entry = GAMES.get((game_type, mode))
        if spec_entry is None or spec_entry.daily is None:
            raise UnsupportedGameError(f"unsupported daily game/mode: {game_type}/{mode}")
        excluding_service: Any = (
            _ExcludingImmichService(self._immich_service, exclude_ids) if exclude_ids else self._immich_service
        )
        return spec_entry.daily.build_spec(mode, excluding_service, settings)
