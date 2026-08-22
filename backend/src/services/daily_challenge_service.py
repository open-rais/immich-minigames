"""
Generates the shared, pre-computed content every player of a (challenge_date, game_type, mode)
plays that day (see persistence/daily.py's DailyChallengeModel). Content generation itself is
entirely delegated to each game's own `games/<game>/daily.py::build_spec()` (games/daily.py's
DailySupport contract) - this module owns only what's genuinely generic across every game: the
challenge date, the advisory lock, the race-safe insert, the cross-day exclusion window, and the
wrapper (_ExcludingImmichService) that applies it.

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
from services.excluding_content_queries import ExcludingContentQueries
from services.immich import ContentQueries, ImmichService
from services.reports_service import ReportsService


class _ExcludingImmichService(ExcludingContentQueries):
    """Widens exclude_ids/exclude_asset_ids with a fixed extra set - the cross-day no-repeat
    window. See services/excluding_content_queries.py's ExcludingContentQueries for the shared
    wrapper shape (composition over ImmichService, __getattr__ passthrough for everything else);
    this subclass only supplies *which* ids that is (the same set regardless of entity kind) and
    this wrapper's two policy choices - no retry-on-empty (an empty pool here is real content
    exhaustion, handled by DailyChallengeService's own outer retry instead) and no `ids=` bypass
    (nothing calls this wrapper with `ids=` set)."""

    def __init__(self, inner: ImmichService, extra_exclude_ids: frozenset[UUID]) -> None:
        super().__init__(inner, retry_without_exclusion=False, bypass_on_explicit_ids=False)
        self._extra_exclude_ids = extra_exclude_ids

    def _asset_exclusion(self) -> frozenset[UUID]:
        return self._extra_exclude_ids

    def _person_exclusion(self) -> frozenset[UUID]:
        return self._extra_exclude_ids

    def _album_exclusion(self) -> frozenset[UUID]:
        return self._extra_exclude_ids


class DailyChallengeService:
    def __init__(
        self, session: Session, immich_service: ImmichService, reports_service: ReportsService | None = None
    ) -> None:
        self._session = session
        self._immich_service = immich_service
        self._daily_settings_service = DailySettingsService(session)
        # Defaults to self-constructing when omitted, same convention as GameFactory's own
        # reports_service - existing callers that predate reports-exclusion keep working.
        self._reports_service = reports_service or ReportsService(session)

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
            # Fallback: the exclusion window, not the library itself, may be what's too tight -
            # retry once with no historical exclusion at all.
            try:
                spec = self._build_spec(game_type, mode, settings, frozenset())
            except ValueError as retry_exc:
                raise NotEnoughContentError(str(retry_exc)) from retry_exc

        # INSERT ... ON CONFLICT DO NOTHING + re-SELECT - if two requests race to generate the
        # same day's first challenge, whichever INSERT lands first wins and the loser just reads
        # that row back, no locking needed.
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
            # MoreOrLess's exclusion_ids() always returns set(), so this naturally stays empty for
            # it without any game-type special case here.
            ids |= spec_entry.daily.exclusion_ids(spec)
        return frozenset(ids)

    def _build_spec(
        self, game_type: str, mode: str, settings: dict[str, float], exclude_ids: frozenset[UUID]
    ) -> dict[str, Any]:
        spec_entry = GAMES.get((game_type, mode))
        if spec_entry is None or spec_entry.daily is None:
            raise UnsupportedGameError(f"unsupported daily game/mode: {game_type}/{mode}")
        excluding_service: ContentQueries = (
            _ExcludingImmichService(self._immich_service, exclude_ids) if exclude_ids else self._immich_service
        )
        # Reports wrap *outside* the no-repeat window: if the reports wrapper's empty-result
        # fallback retries without report exclusion, it still goes through excluding_service and
        # so still respects the window. The reverse nesting (window outside reports) would let a
        # report-emptied pool silently drop the window too when that fallback fires.
        content_source = self._reports_service.filter_for(excluding_service, game_type, mode)
        return spec_entry.daily.build_spec(mode, content_source, settings)
