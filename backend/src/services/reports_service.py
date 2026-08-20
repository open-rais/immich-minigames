"""
Metadata-reporting feature: a player flags a person/album/asset as having bad metadata; an admin
reviews the open reports and marks them resolved.

`reason`/`entity_type` are plain strings here, not an enum - the shared vocabulary
(`ReportReason`/`ReportEntity`) lives in games/report_spec.py, which is what the future round-
generation exclusion (not implemented yet) will use to decide which reasons matter to which
(game_type, mode). This service and its persistence stay decoupled from that - it just stores and
groups whatever reason strings it's given.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from audit import audit
from persistence.reports import ReportModel


class ReportNotFoundError(Exception):
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
        site exists yet)."""
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
        `reasons` short-circuits without a query - the future round-generation wrapper calls this
        once per (game_type, mode), and a mode with no reasons that apply to it is the common case
        it would otherwise pay a pointless `IN ()` query for."""
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
