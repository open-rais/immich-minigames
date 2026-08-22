"""
Metadata-reporting feature: a player flags a person/album/asset as having bad metadata; an admin
reviews the open reports and marks them resolved.

`reason`/`entity_type` are plain strings on every method's signature (not the games/report_spec.py
enums) - persistence and the read paths (list/counts/open_ids_for) don't need to know the fixed
vocabulary, only create() does, to reject a reason that doesn't belong to the given entity_type.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from audit import audit
from games.report_spec import REASON_ENTITY, ReportEntity, ReportReason
from games.reports_registry import REPORT_EXCLUSIONS
from persistence.reports import ReportModel
from services.immich import ContentQueries


class ReportNotFoundError(Exception):
    pass


class InvalidReportReasonError(Exception):
    pass


@dataclass(frozen=True)
class ReportExclusions:
    """Open report ids grouped by the entity type they point at - a plain frozenset[UUID] isn't
    enough because a report's `entity_id` can collide in value space across entity types (an
    asset and a person could in principle share a UUID)."""

    asset_ids: frozenset[UUID] = frozenset()
    person_ids: frozenset[UUID] = frozenset()
    album_ids: frozenset[UUID] = frozenset()


class ReportsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, user_id: UUID, entity_type: str, entity_id: UUID, reasons: list[str], note: str | None
    ) -> None:
        """One row per reason, in a single INSERT ... ON CONFLICT DO NOTHING against the partial
        unique index - reporting the same (user, entity, reason) again while it's still open is a
        silent no-op. `reasons` is assumed non-empty (the API DTO validates that; no other call
        site exists yet).

        Raises InvalidReportReasonError, before touching the DB, if any reason doesn't belong to
        entity_type (e.g. "asset_date" on a person) - all-or-nothing, not a partial insert of the
        valid ones."""
        for reason in reasons:
            if REASON_ENTITY[ReportReason(reason)] != ReportEntity(entity_type):
                raise InvalidReportReasonError(f"reason {reason!r} does not apply to entity_type {entity_type!r}")

        stmt = (
            pg_insert(ReportModel)
            .values(
                [
                    {
                        "id": uuid4(),
                        "user_id": user_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "reason": reason,
                        "note": note,
                    }
                    for reason in reasons
                ]
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "entity_type", "entity_id", "reason"],
                index_where=sa.text("NOT solved"),
            )
        )
        self._session.execute(stmt)
        self._session.commit()
        audit(
            "report_created",
            entity_type=entity_type,
            entity_id=str(entity_id),
            reasons=reasons,
            user_id=str(user_id),
        )

    def list(self, entity_type: str, solved: bool, *, offset: int = 0, limit: int = 20) -> list[ReportModel]:
        stmt = (
            sa.select(ReportModel)
            .where(ReportModel.entity_type == entity_type, ReportModel.solved == solved)
            .order_by(ReportModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def counts(self) -> dict[str, int]:
        """Open-report count per entity_type. Entity types with zero open reports are simply
        absent from the result - no zero-fill here, since the fixed set of valid entity types
        isn't this module's vocabulary to know (see the module docstring); a caller that needs
        every key present zero-fills against its own known set."""
        stmt = (
            sa.select(ReportModel.entity_type, sa.func.count())
            .where(~ReportModel.solved)
            .group_by(ReportModel.entity_type)
        )
        return dict(self._session.execute(stmt).all())

    def set_solved(self, report_id: UUID, solved: bool) -> ReportModel:
        report = self._session.get(ReportModel, report_id)
        if report is None:
            raise ReportNotFoundError(f"report {report_id} not found")
        report.solved = solved
        report.solved_at = datetime.now(UTC) if solved else None
        self._session.commit()
        audit("report_resolved", report_id=str(report_id), solved=solved)
        return report

    def open_ids_for(self, reasons: Iterable[str]) -> ReportExclusions:
        """Groups open reports' entity ids by entity_type, restricted to the given reasons. Empty
        `reasons` short-circuits without a query - filter_for below calls this once per
        (game_type, mode), and a mode with no reasons that apply to it is the common case it would
        otherwise pay a pointless `IN ()` query for."""
        reasons = list(reasons)
        if not reasons:
            return ReportExclusions()

        stmt = sa.select(ReportModel.entity_type, ReportModel.entity_id).where(
            ~ReportModel.solved, ReportModel.reason.in_(reasons)
        )
        asset_ids: set[UUID] = set()
        person_ids: set[UUID] = set()
        album_ids: set[UUID] = set()
        by_type = {"asset": asset_ids, "person": person_ids, "album": album_ids}
        for entity_type, entity_id in self._session.execute(stmt):
            by_type[entity_type].add(entity_id)
        return ReportExclusions(
            asset_ids=frozenset(asset_ids), person_ids=frozenset(person_ids), album_ids=frozenset(album_ids)
        )

    def filter_for(self, immich_service: ContentQueries, game_type: str, mode: str) -> ContentQueries:
        """Wraps immich_service so live round generation for (game_type, mode) skips entities with
        an open report relevant to it (games/reports_registry.py decides which reasons apply to
        which mode). Returns immich_service unwrapped - not _ReportsExcludingImmichService(...,
        ReportExclusions()) - whenever there's nothing to actually filter, so the common case (a
        mode with no applicable reasons, or one with reasons but no open reports right now) costs
        nothing beyond this one query."""
        reasons = REPORT_EXCLUSIONS.get((game_type, mode), frozenset())
        if not reasons:
            return immich_service
        exclusions = self.open_ids_for(reasons)
        if not (exclusions.asset_ids or exclusions.person_ids or exclusions.album_ids):
            return immich_service
        return _ReportsExcludingImmichService(immich_service, exclusions)


class _ReportsExcludingImmichService:
    """Wraps a ContentQueries so a sampling call skips entities under an open, relevant report -
    composition (not a subclass), same shape as daily_challenge_service.py's
    _ExcludingImmichService. Two rules that one doesn't need:

    - `ids=` means "resolve this concrete id" (a guess lookup), never "sample the pool" - passed
      straight through unfiltered, so a reported entity stays guessable/searchable even while
      excluded from being the thing to guess.
    - If a sampling call comes back empty *because* of this exclusion, it retries once without it -
      a report is a best-effort nudge, not a hard guarantee that could otherwise stall a game
      mid-run just because its whole remaining pool happens to be reported.

    Everything else (thumbnails, search_persons/search_albums, per-id clue queries like
    get_assets_together_count) is forwarded straight through via __getattr__, unfiltered - see
    ReportsService.filter_for's docstring and games/report_spec.py for why."""

    def __init__(self, inner: ContentQueries, exclusions: ReportExclusions) -> None:
        self._inner = inner
        self._exclusions = exclusions

    def get_assets(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None:
            return self._inner.get_assets(ids=ids, exclude_ids=exclude_ids, **kwargs)
        result = self._inner.get_assets(exclude_ids=exclude_ids | self._exclusions.asset_ids, **kwargs)
        if not result and self._exclusions.asset_ids:
            result = self._inner.get_assets(exclude_ids=exclude_ids, **kwargs)
        return result

    def get_persons(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None:
            return self._inner.get_persons(ids=ids, exclude_ids=exclude_ids, **kwargs)
        result = self._inner.get_persons(exclude_ids=exclude_ids | self._exclusions.person_ids, **kwargs)
        if not result and self._exclusions.person_ids:
            result = self._inner.get_persons(exclude_ids=exclude_ids, **kwargs)
        return result

    def get_albums(
        self, *, ids: frozenset[UUID] | None = None, exclude_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        if ids is not None:
            return self._inner.get_albums(ids=ids, exclude_ids=exclude_ids, **kwargs)
        result = self._inner.get_albums(exclude_ids=exclude_ids | self._exclusions.album_ids, **kwargs)
        if not result and self._exclusions.album_ids:
            result = self._inner.get_albums(exclude_ids=exclude_ids, **kwargs)
        return result

    def get_random_asset_with_named_faces(
        self, *, exclude_asset_ids: frozenset[UUID] = frozenset(), **kwargs: Any
    ) -> Any:
        result = self._inner.get_random_asset_with_named_faces(
            exclude_asset_ids=exclude_asset_ids | self._exclusions.asset_ids,
            exclude_person_ids=self._exclusions.person_ids,
            **kwargs,
        )
        if not result and (self._exclusions.asset_ids or self._exclusions.person_ids):
            result = self._inner.get_random_asset_with_named_faces(exclude_asset_ids=exclude_asset_ids, **kwargs)
        return result

    def has_named_faces_asset(self, *, exclude_asset_ids: frozenset[UUID] = frozenset(), **kwargs: Any) -> Any:
        result = self._inner.has_named_faces_asset(
            exclude_asset_ids=exclude_asset_ids | self._exclusions.asset_ids,
            exclude_person_ids=self._exclusions.person_ids,
            **kwargs,
        )
        if not result and (self._exclusions.asset_ids or self._exclusions.person_ids):
            result = self._inner.has_named_faces_asset(exclude_asset_ids=exclude_asset_ids, **kwargs)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
