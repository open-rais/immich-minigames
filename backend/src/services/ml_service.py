"""
Immich-ML data access - reads face-embedding data Immich-ML already computed and stored in
Immich's own Postgres (`face_search.embedding`, `vector(512)`, pgvector cosine ops) rather than
calling Immich-ML live - see docs/ARCHITECTURE/IMMICH.md's "face_search" section for why
(immich-machine-learning isn't reachable from the host in the dev stack).
"""

import logging
from dataclasses import dataclass
from uuid import UUID

import numpy as np
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, Row

from perf import timed
from persistence.album_ml_cache import AlbumEmbeddingCacheModel
from persistence.base import get_app_engine
from persistence.immich_db import get_immich_engine
from persistence.immich_tables import album, album_asset, asset_face, person
from persistence.ml_cache import PersonFaceEmbeddingCacheModel

_CACHE_TABLE = PersonFaceEmbeddingCacheModel.__table__
_ALBUM_CACHE_TABLE = AlbumEmbeddingCacheModel.__table__

# Visible, non-deleted faces are the same eligibility filter used everywhere else a person's faces
# are counted/read (see services/immich/faces.py's get_random_asset_with_named_faces).
_FACE_COUNT_QUERY = text("""
    SELECT count(*) FROM asset_face
    WHERE "personId" = :person_id AND "deletedAt" IS NULL AND "isVisible"
""")

# Element-wise average over every visible face's embedding for this person (pgvector's own
# `avg(vector)` aggregate, added in pgvector 0.5+) - a more robust representative embedding than a
# single profile photo, without going back to the O(n*m) cost of comparing every face pair between
# two people (see PersonFaceEmbeddingCacheModel's module docstring). Cast to ::text explicitly so
# the driver hands back a deterministic "[v1,v2,...]" string regardless of whether a pgvector
# adapter is registered on this connection - matches pgvector's own input format, parsed back by
# hand in _get_person_embedding rather than pulling in the `pgvector` package for one read.
_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(fs.embedding)::text
    FROM asset_face af
    JOIN face_search fs ON fs."faceId" = af.id
    WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible"
""")


def _parse_vector_text(value: str) -> list[float]:
    """Parses pgvector's own `[v1,v2,...]` text output format - see _AVG_EMBEDDING_QUERY."""
    return [float(v) for v in value.strip()[1:-1].split(",")]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@dataclass(frozen=True)
class StaleIds:
    """Result of a whole-universe staleness diff (see stale_person_ids/stale_album_ids). `ids` is
    the subset that actually needs (re)computing - what a "process missing" run should touch.
    `all_ids` is every id in the universe regardless of staleness - what a "reprocess all" run
    needs instead, since a merge/split can leave a cached embedding wrong without ever changing
    the fingerprint (see the freshness check's own cheap-not-exact tradeoff). `total` (`=
    len(all_ids)`) is the denominator for the admin panel's coverage counter - it has to be the
    eligible-only denominator, not every person/album, or coverage would never read 100%."""

    ids: frozenset[UUID]
    all_ids: frozenset[UUID]
    total: int


# Raw album_asset row count - a cheap staleness fingerprint for the album embedding cache, same
# "cheap not exact" spirit as _FACE_COUNT_QUERY (not the eligibility-filtered count get_albums'
# asset_count column computes - this only needs to notice "something changed", not be exact).
_ALBUM_ASSET_COUNT_QUERY = text("""SELECT count(*) FROM album_asset WHERE "albumId" = :album_id""")

# Element-wise average over every eligible asset's CLIP embedding (Immich's `smart_search` table -
# semantic/text-search embeddings, distinct from `face_search`) for this album - powers Albumdle's
# similarity clue (roadmap #14). Joins through `asset` and applies the standard eligibility filter
# because `album_asset` rows outlive Immich's soft-delete (deletedAt/status live on `asset`, not
# `album_asset`) - see docs/ARCHITECTURE/IMMICH.md's "standard eligibility filter". `smart_search`
# isn't declared as a Core Table() for the same reason `face_search` isn't (see
# persistence/immich_tables.py's docstring) - only raw SQL ever touches its pgvector column.
_ALBUM_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(ss.embedding)::text
    FROM album_asset aa
    JOIN asset a ON a.id = aa."assetId"
        AND a.status = 'active' AND a.visibility = 'timeline' AND a."deletedAt" IS NULL
    JOIN smart_search ss ON ss."assetId" = aa."assetId"
    WHERE aa."albumId" = :album_id
""")


class MLService:
    def __init__(self, engine: Engine | None = None, app_engine: Engine | None = None) -> None:
        self._engine = engine or get_immich_engine()
        # This app's own database (not Immich's, which is read-only for this app's DB role) - see
        # persistence/ml_cache.py for why the embedding cache has to live here.
        self._app_engine = app_engine or get_app_engine()

    def _person_face_count(self, person_id: UUID) -> int:
        """The freshness fingerprint: how many visible, non-deleted faces this person currently
        has in Immich."""
        with self._engine.connect() as conn:
            return conn.execute(_FACE_COUNT_QUERY, {"person_id": str(person_id)}).scalar_one()

    def _read_person_cache_row(self, person_id: UUID) -> Row | None:
        with self._app_engine.connect() as conn:
            return conn.execute(
                sa.select(_CACHE_TABLE.c.embedding, _CACHE_TABLE.c.face_count).where(
                    _CACHE_TABLE.c.person_id == person_id
                )
            ).first()

    def _compute_person_embedding_vector(self, person_id: UUID) -> list[float] | None:
        """The actual pgvector average over Immich's `face_search` rows - the expensive part that
        the cache exists to avoid paying on every guess. None when none of this person's visible
        faces has a `face_search` row yet (e.g. Immich-ML hasn't processed them) - nothing to
        average, mirroring _compute_album_embedding_vector's own smart_search gap."""
        with self._engine.connect() as conn:
            avg_text = conn.execute(_AVG_EMBEDDING_QUERY, {"person_id": str(person_id)}).scalar_one()
        return _parse_vector_text(avg_text) if avg_text is not None else None

    def _save_person_embedding(self, person_id: UUID, embedding: list[float], face_count: int) -> None:
        with self._app_engine.begin() as conn:
            upsert = pg_insert(_CACHE_TABLE).values(person_id=person_id, embedding=embedding, face_count=face_count)
            upsert = upsert.on_conflict_do_update(
                index_elements=[_CACHE_TABLE.c.person_id],
                set_={
                    "embedding": upsert.excluded.embedding,
                    "face_count": upsert.excluded.face_count,
                    "computed_at": sa.func.now(),
                },
            )
            conn.execute(upsert)

    def _clear_person_cache(self, person_id: UUID) -> None:
        with self._app_engine.begin() as conn:
            conn.execute(sa.delete(_CACHE_TABLE).where(_CACHE_TABLE.c.person_id == person_id))

    def _get_person_embedding(self, person_id: UUID, *, force: bool = False) -> np.ndarray | None:
        """This person's representative face embedding - the element-wise average across their
        currently visible, non-deleted faces - served from `person_face_embedding_cache` when
        still fresh (see that table's module docstring for the face-count-based freshness check),
        recomputed and cached otherwise. None if the person currently has no visible faces at all
        (nothing to average, and any stale cache row for them is deleted rather than left behind).
        `force=True` skips the freshness check and always recomputes - the admin "reprocess all"
        path, reached via compute_person_embedding below."""
        current_count = self._person_face_count(person_id)

        if current_count == 0:
            self._clear_person_cache(person_id)
            return None

        if not force:
            cached = self._read_person_cache_row(person_id)
            if cached is not None and cached.face_count == current_count:
                return np.array(cached.embedding, dtype=np.float32)

        # INFO, not DEBUG: a recompute (cache miss or stale, or a forced reprocess) is rare and
        # intrinsically interesting on a live instance - a hit is the common case and stays
        # unlogged.
        with timed(
            "ml.recompute_embedding", level=logging.INFO, entity="person", id=str(person_id), face_count=current_count
        ):
            embedding = self._compute_person_embedding_vector(person_id)
            if embedding is None:
                # Every visible face lacks a face_search row (Immich-ML hasn't processed them yet)
                # - nothing to average, so this behaves like the "no faces at all" case above
                # rather than crashing on a NULL avg() or caching a stale/garbage vector.
                self._clear_person_cache(person_id)
                return None
            self._save_person_embedding(person_id, embedding, current_count)

        return np.array(embedding, dtype=np.float32)

    def compute_person_embedding(self, person_id: UUID, *, force: bool = False) -> np.ndarray | None:
        """Public entry point for the admin embedding worker to (re)compute one person's cached
        embedding - see _get_person_embedding for the actual cache/recompute contract."""
        return self._get_person_embedding(person_id, force=force)

    def face_similarity(self, person_a_id: UUID, person_b_id: UUID) -> float | None:
        """Face-similarity (cosine, mathematically -1..1 though unrelated faces usually land near
        0 - slightly negative is normal, not a bug, see docs/ARCHITECTURE/IMMICH.md's face_search
        section) between person_a's and person_b's representative face embeddings (see
        _get_person_embedding) - None if either currently has no visible faces. Powers Immichdle's
        MLSimilarity clue."""
        if person_a_id == person_b_id:
            return 1.0
        embedding_a = self._get_person_embedding(person_a_id)
        embedding_b = self._get_person_embedding(person_b_id)
        if embedding_a is None or embedding_b is None:
            return None
        return _cosine_similarity(embedding_a, embedding_b)

    def stale_person_ids(self, *, eligible_only: bool = True) -> StaleIds:
        """Which people need their embedding (re)computed, without an N+1 Immich round-trip: one
        query for every person's current face count, one query for every cached row, diffed in
        Python. `eligible_only` restricts the universe to the people a game can actually
        target/guess (named, not hidden, with a thumbnail - the same filter
        get_persons(named_only=True) applies) - the admin panel's default; the "include
        unnamed/hidden" checkbox passes False for the full person universe."""
        stmt = (
            sa.select(person.c.id, sa.func.count(sa.func.distinct(asset_face.c.id)).label("face_count"))
            .select_from(
                person.outerjoin(
                    asset_face,
                    (asset_face.c.personId == person.c.id)
                    & asset_face.c.deletedAt.is_(None)
                    & asset_face.c.isVisible.is_(True),
                )
            )
            .group_by(person.c.id)
        )
        if eligible_only:
            stmt = stmt.where(person.c.isHidden.is_(False), person.c.thumbnailPath != "", person.c.name != "")
        with self._engine.connect() as conn:
            current_counts = {row.id: row.face_count for row in conn.execute(stmt)}

        with self._app_engine.connect() as conn:
            cached_counts = {
                row.person_id: row.face_count
                for row in conn.execute(sa.select(_CACHE_TABLE.c.person_id, _CACHE_TABLE.c.face_count))
            }

        stale = frozenset(
            person_id for person_id, count in current_counts.items() if cached_counts.get(person_id) != count
        )
        return StaleIds(ids=stale, all_ids=frozenset(current_counts), total=len(current_counts))

    def _album_asset_count(self, album_id: UUID) -> int:
        """The freshness fingerprint: raw `album_asset` row count, not the eligibility-filtered
        count used elsewhere (see _ALBUM_ASSET_COUNT_QUERY's own comment)."""
        with self._engine.connect() as conn:
            return conn.execute(_ALBUM_ASSET_COUNT_QUERY, {"album_id": str(album_id)}).scalar_one()

    def _read_album_cache_row(self, album_id: UUID) -> Row | None:
        with self._app_engine.connect() as conn:
            return conn.execute(
                sa.select(_ALBUM_CACHE_TABLE.c.embedding, _ALBUM_CACHE_TABLE.c.asset_count).where(
                    _ALBUM_CACHE_TABLE.c.album_id == album_id
                )
            ).first()

    def _compute_album_embedding_vector(self, album_id: UUID) -> list[float] | None:
        """The actual CLIP average over Immich's `smart_search` rows. None when every asset in the
        album is either ineligible or has no `smart_search` row yet - nothing to average."""
        with self._engine.connect() as conn:
            avg_text = conn.execute(_ALBUM_AVG_EMBEDDING_QUERY, {"album_id": str(album_id)}).scalar_one()
        return _parse_vector_text(avg_text) if avg_text is not None else None

    def _save_album_embedding(self, album_id: UUID, embedding: list[float], asset_count: int) -> None:
        with self._app_engine.begin() as conn:
            upsert = pg_insert(_ALBUM_CACHE_TABLE).values(
                album_id=album_id, embedding=embedding, asset_count=asset_count
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=[_ALBUM_CACHE_TABLE.c.album_id],
                set_={
                    "embedding": upsert.excluded.embedding,
                    "asset_count": upsert.excluded.asset_count,
                    "computed_at": sa.func.now(),
                },
            )
            conn.execute(upsert)

    def _clear_album_cache(self, album_id: UUID) -> None:
        with self._app_engine.begin() as conn:
            conn.execute(sa.delete(_ALBUM_CACHE_TABLE).where(_ALBUM_CACHE_TABLE.c.album_id == album_id))

    def _get_album_embedding(self, album_id: UUID, *, force: bool = False) -> np.ndarray | None:
        """This album's representative CLIP embedding - the element-wise average across its
        currently eligible assets' `smart_search` embeddings - served from
        `album_embedding_cache` when still fresh (see that table's module docstring), recomputed
        and cached otherwise. None if the album currently has no assets at all (nothing to
        average, and any stale cache row is deleted rather than left behind). `force=True` skips
        the freshness check and always recomputes - the admin "reprocess all" path, reached via
        compute_album_embedding below."""
        current_count = self._album_asset_count(album_id)

        if current_count == 0:
            self._clear_album_cache(album_id)
            return None

        if not force:
            cached = self._read_album_cache_row(album_id)
            if cached is not None and cached.asset_count == current_count:
                return np.array(cached.embedding, dtype=np.float32)

        # INFO, not DEBUG: a recompute (cache miss or stale, or a forced reprocess) is rare and
        # intrinsically interesting on a live instance - a hit is the common case and stays
        # unlogged.
        with timed(
            "ml.recompute_embedding", level=logging.INFO, entity="album", id=str(album_id), asset_count=current_count
        ):
            embedding = self._compute_album_embedding_vector(album_id)
            if embedding is None:
                # Every asset in the album is either ineligible (soft-deleted/archived/hidden) or has
                # no smart_search row yet (e.g. Immich-ML hasn't processed it) - nothing to average, so
                # this behaves like the "no assets at all" case above rather than caching a vector.
                self._clear_album_cache(album_id)
                return None
            self._save_album_embedding(album_id, embedding, current_count)

        return np.array(embedding, dtype=np.float32)

    def compute_album_embedding(self, album_id: UUID, *, force: bool = False) -> np.ndarray | None:
        """Public entry point for the admin embedding worker to (re)compute one album's cached
        embedding - see _get_album_embedding for the actual cache/recompute contract."""
        return self._get_album_embedding(album_id, force=force)

    def album_similarity(self, album_a_id: UUID, album_b_id: UUID) -> float | None:
        """Cosine similarity between two albums' averaged CLIP embeddings (see
        _get_album_embedding) - None if either currently has no eligible assets with a
        smart_search embedding. Powers Albumdle's similarity clue."""
        if album_a_id == album_b_id:
            return 1.0
        embedding_a = self._get_album_embedding(album_a_id)
        embedding_b = self._get_album_embedding(album_b_id)
        if embedding_a is None or embedding_b is None:
            return None
        return _cosine_similarity(embedding_a, embedding_b)

    def stale_album_ids(self) -> StaleIds:
        """Which albums need their embedding (re)computed - same two-query diff as
        stale_person_ids, no eligible_only: unlike persons, every non-deleted album is in scope,
        there's no "unnamed/hidden" carve-out for albums.
        Non-deleted albums with zero `album_asset` rows are included in `total` (as 0) - they're
        legitimately part of the universe, just never stale since there's nothing to compute."""
        stmt = (
            sa.select(album.c.id, sa.func.count(album_asset.c.assetId).label("asset_count"))
            .select_from(album.outerjoin(album_asset, album_asset.c.albumId == album.c.id))
            .where(album.c.deletedAt.is_(None))
            .group_by(album.c.id)
        )
        with self._engine.connect() as conn:
            current_counts = {row.id: row.asset_count for row in conn.execute(stmt)}

        with self._app_engine.connect() as conn:
            cached_counts = {
                row.album_id: row.asset_count
                for row in conn.execute(sa.select(_ALBUM_CACHE_TABLE.c.album_id, _ALBUM_CACHE_TABLE.c.asset_count))
            }

        stale = frozenset(
            album_id for album_id, count in current_counts.items() if cached_counts.get(album_id) != count
        )
        return StaleIds(ids=stale, all_ids=frozenset(current_counts), total=len(current_counts))
