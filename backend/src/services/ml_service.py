"""
Immich-ML data access - reads face-embedding data Immich-ML already computed and stored in
Immich's own Postgres (`face_search.embedding`, `vector(512)`, pgvector cosine ops) rather than
calling Immich-ML live - see docs/ARCHITECTURE/IMMICH.md's "face_search" section for why
(immich-machine-learning isn't reachable from the host in the dev stack).
"""

import logging
from dataclasses import dataclass
from datetime import datetime
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

# `now()` as seen by Immich's own database - the watermark taken before any vector is read for a
# (re)computation (see persistence/ml_cache.py's module docstring for why it has to come from this
# specific connection, not the app's own database or Python's local clock).
_NOW_QUERY = text("SELECT now()")

# Visible, non-deleted faces are the same eligibility filter used everywhere else a person's faces
# are counted/read (see services/immich/faces.py's get_random_asset_with_named_faces).
_FACE_COUNT_QUERY = text("""
    SELECT count(*) FROM asset_face
    WHERE "personId" = :person_id AND "deletedAt" IS NULL AND "isVisible"
""")

# Same filter as _FACE_COUNT_QUERY, restricted to faces that already existed (by updatedAt) at the
# given watermark - "still part of whatever the cached average was last computed from".
_PERSON_INTACT_COUNT_QUERY = text("""
    SELECT count(*) FROM asset_face
    WHERE "personId" = :person_id AND "deletedAt" IS NULL AND "isVisible" AND "updatedAt" <= :watermark
""")

# Element-wise average over every visible face's embedding for this person (pgvector's own
# `avg(vector)` aggregate, added in pgvector 0.5+) - a more robust representative embedding than a
# single profile photo, without going back to the O(n*m) cost of comparing every face pair between
# two people (see PersonFaceEmbeddingCacheModel's module docstring). Cast to ::text explicitly so
# the driver hands back a deterministic "[v1,v2,...]" string regardless of whether a pgvector
# adapter is registered on this connection - matches pgvector's own input format, parsed back by
# hand in _get_person_embedding rather than pulling in the `pgvector` package for one read. Also
# returns the row count actually averaged over - the join can come up short of the visible-face
# count above when Immich-ML hasn't embedded every face yet, and that count is what has to be
# stored as `embedding_count`, not the (possibly larger) fingerprint.
_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(fs.embedding)::text AS avg_embedding, count(*) AS embedding_count
    FROM asset_face af
    JOIN face_search fs ON fs."faceId" = af.id
    WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible"
""")

# Same join as _AVG_EMBEDDING_QUERY, restricted to faces added since the given watermark - the
# "new" side of the incremental weighted-average update (see _try_incremental_person_update).
_PERSON_NEW_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(fs.embedding)::text AS avg_embedding, count(*) AS new_count
    FROM asset_face af
    JOIN face_search fs ON fs."faceId" = af.id
    WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible" AND af."updatedAt" > :watermark
""")


def _parse_vector_text(value: str) -> list[float]:
    """Parses pgvector's own `[v1,v2,...]` text output format - see _AVG_EMBEDDING_QUERY."""
    return [float(v) for v in value.strip()[1:-1].split(",")]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def merge_weighted_average(
    old_embedding: list[float], old_count: int, new_embedding: list[float], new_count: int
) -> list[float]:
    """Element-wise weighted average of two already-averaged vectors, weighted by how many raw
    vectors each was itself averaged from. Mathematically exact, not an approximation: the mean of
    a union of two disjoint sets equals the count-weighted mean of the two sets' own means - so
    folding newly added faces/assets into a cached average this way gives the identical result a
    full recompute over the union would. Pure/no I/O on purpose, so the arithmetic itself is
    testable against synthetic vectors without a database.

    Repeated merging accumulates ordinary float rounding error over many generations - negligible
    next to the similarity clues' comparison thresholds, and "reprocess all" (compute_person_
    embedding/compute_album_embedding with force=True) resets it to zero by recomputing from
    scratch, which is one of the reasons that path exists."""
    old = np.asarray(old_embedding, dtype=np.float64)
    new = np.asarray(new_embedding, dtype=np.float64)
    total = old_count + new_count
    return ((old * old_count + new * new_count) / total).tolist()


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

# Same filter as _ALBUM_ASSET_COUNT_QUERY (deliberately not eligibility-filtered - see that query's
# own comment), restricted to album_asset rows that already existed (by updatedAt) at the given
# watermark.
_ALBUM_INTACT_COUNT_QUERY = text("""
    SELECT count(*) FROM album_asset WHERE "albumId" = :album_id AND "updatedAt" <= :watermark
""")

# Element-wise average over every eligible asset's CLIP embedding (Immich's `smart_search` table -
# semantic/text-search embeddings, distinct from `face_search`) for this album - powers Albumdle's
# similarity clue (roadmap #14). Joins through `asset` and applies the standard eligibility filter
# because `album_asset` rows outlive Immich's soft-delete (deletedAt/status live on `asset`, not
# `album_asset`) - see docs/ARCHITECTURE/IMMICH.md's "standard eligibility filter". `smart_search`
# isn't declared as a Core Table() for the same reason `face_search` isn't (see
# persistence/immich_tables.py's docstring) - only raw SQL ever touches its pgvector column. Also
# returns the row count actually averaged over, same reasoning as _AVG_EMBEDDING_QUERY's own count
# - this one can come up short of asset_count for two independent reasons (ineligible assets *and*
# missing smart_search rows), not just one.
_ALBUM_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(ss.embedding)::text AS avg_embedding, count(*) AS embedding_count
    FROM album_asset aa
    JOIN asset a ON a.id = aa."assetId"
        AND a.status = 'active' AND a.visibility = 'timeline' AND a."deletedAt" IS NULL
    JOIN smart_search ss ON ss."assetId" = aa."assetId"
    WHERE aa."albumId" = :album_id
""")

# Same join as _ALBUM_AVG_EMBEDDING_QUERY, restricted to album_asset rows added since the given
# watermark - the "new" side of the incremental weighted-average update.
_ALBUM_NEW_AVG_EMBEDDING_QUERY = text("""
    SELECT avg(ss.embedding)::text AS avg_embedding, count(*) AS new_count
    FROM album_asset aa
    JOIN asset a ON a.id = aa."assetId"
        AND a.status = 'active' AND a.visibility = 'timeline' AND a."deletedAt" IS NULL
    JOIN smart_search ss ON ss."assetId" = aa."assetId"
    WHERE aa."albumId" = :album_id AND aa."updatedAt" > :watermark
""")


class MLService:
    def __init__(self, engine: Engine | None = None, app_engine: Engine | None = None) -> None:
        self._engine = engine or get_immich_engine()
        # This app's own database (not Immich's, which is read-only for this app's DB role) - see
        # persistence/ml_cache.py for why the embedding cache has to live here.
        self._app_engine = app_engine or get_app_engine()

    def _watermark(self) -> datetime:
        with self._engine.connect() as conn:
            return conn.execute(_NOW_QUERY).scalar_one()

    def _person_face_count(self, person_id: UUID) -> int:
        """The freshness fingerprint: how many visible, non-deleted faces this person currently
        has in Immich."""
        with self._engine.connect() as conn:
            return conn.execute(_FACE_COUNT_QUERY, {"person_id": str(person_id)}).scalar_one()

    def _person_intact_count(self, person_id: UUID, watermark: datetime) -> int:
        """How many of this person's currently visible faces already existed (by `updatedAt`) as
        of `watermark` - i.e. weren't added or edited since a cached average computed as of that
        same watermark. Used only to decide whether that cached average can be trusted as the
        incremental update's starting point (see _try_incremental_person_update)."""
        with self._engine.connect() as conn:
            return conn.execute(
                _PERSON_INTACT_COUNT_QUERY, {"person_id": str(person_id), "watermark": watermark}
            ).scalar_one()

    def _read_person_cache_row(self, person_id: UUID) -> Row | None:
        with self._app_engine.connect() as conn:
            return conn.execute(
                sa.select(
                    _CACHE_TABLE.c.embedding,
                    _CACHE_TABLE.c.face_count,
                    _CACHE_TABLE.c.embedding_count,
                    _CACHE_TABLE.c.computed_at,
                ).where(_CACHE_TABLE.c.person_id == person_id)
            ).first()

    def _compute_person_embedding_vector(self, person_id: UUID) -> tuple[list[float], int] | None:
        """The actual pgvector average over Immich's `face_search` rows - the expensive part that
        the cache exists to avoid paying on every guess - plus how many rows it was averaged over
        (see _AVG_EMBEDDING_QUERY's own comment for why that can differ from the face count).
        None when none of this person's visible faces has a `face_search` row yet (e.g. Immich-ML
        hasn't processed them) - nothing to average, mirroring
        _compute_album_embedding_vector's own smart_search gap."""
        with self._engine.connect() as conn:
            row = conn.execute(_AVG_EMBEDDING_QUERY, {"person_id": str(person_id)}).one()
        if row.avg_embedding is None:
            return None
        return _parse_vector_text(row.avg_embedding), row.embedding_count

    def _try_incremental_person_update(self, person_id: UUID, cached: Row) -> tuple[list[float], int] | None:
        """Folds faces added since `cached`'s own watermark into its average instead of
        recomputing from scratch over every visible face again - mathematically exact when it
        applies (see merge_weighted_average). None whenever the guard doesn't pass: the cached row
        predates this column (embedding_count unknown) or its face set isn't provably a pure
        subset of the current one (something was removed or edited, not just added - see
        persistence/ml_cache.py's docstring for why an edit falls out of "intact" the same way a
        removal does). The caller falls back to a full recompute in that case, always correct,
        just not free."""
        if cached.embedding_count is None:
            return None
        intact_count = self._person_intact_count(person_id, cached.computed_at)
        if intact_count != cached.embedding_count:
            return None

        with self._engine.connect() as conn:
            new = conn.execute(
                _PERSON_NEW_AVG_EMBEDDING_QUERY, {"person_id": str(person_id), "watermark": cached.computed_at}
            ).one()
        if new.avg_embedding is None:
            # Some face was added/edited (updatedAt > watermark), but none of them has a
            # face_search row yet - the cached average is still exactly right as-is, just needs
            # its fingerprint refreshed (by the caller) so this check doesn't repeat every request.
            return list(cached.embedding), cached.embedding_count

        new_embedding = _parse_vector_text(new.avg_embedding)
        merged = merge_weighted_average(list(cached.embedding), cached.embedding_count, new_embedding, new.new_count)
        return merged, cached.embedding_count + new.new_count

    def _save_person_embedding(
        self, person_id: UUID, embedding: list[float], face_count: int, embedding_count: int, computed_at: datetime
    ) -> None:
        with self._app_engine.begin() as conn:
            upsert = pg_insert(_CACHE_TABLE).values(
                person_id=person_id,
                embedding=embedding,
                face_count=face_count,
                embedding_count=embedding_count,
                computed_at=computed_at,
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=[_CACHE_TABLE.c.person_id],
                set_={
                    "embedding": upsert.excluded.embedding,
                    "face_count": upsert.excluded.face_count,
                    "embedding_count": upsert.excluded.embedding_count,
                    "computed_at": upsert.excluded.computed_at,
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
        `force=True` skips the freshness check *and* the incremental path below, and always does a
        full recompute - the admin "reprocess all" path, reached via compute_person_embedding
        below, and the only way to fix a merge/split that left the count unchanged (see
        stale_person_ids' own docstring)."""
        current_count = self._person_face_count(person_id)

        if current_count == 0:
            self._clear_person_cache(person_id)
            return None

        cached = None if force else self._read_person_cache_row(person_id)
        if cached is not None and cached.face_count == current_count:
            return np.array(cached.embedding, dtype=np.float32)

        # Taken now, before reading any vector below, regardless of which path this ends up
        # taking - see persistence/ml_cache.py's docstring for why the ordering matters.
        watermark = self._watermark()
        incremental = None if cached is None else self._try_incremental_person_update(person_id, cached)
        mode = "incremental" if incremental is not None else "full"

        # INFO, not DEBUG: a recompute (cache miss or stale, or a forced reprocess) is rare and
        # intrinsically interesting on a live instance - a hit is the common case and stays
        # unlogged. `mode` distinguishes the incremental fast path from a full recompute, so it's
        # visible from the logs alone whether the guard is actually paying off in practice.
        with timed(
            "ml.recompute_embedding",
            level=logging.INFO,
            entity="person",
            id=str(person_id),
            face_count=current_count,
            mode=mode,
        ):
            if incremental is not None:
                embedding, embedding_count = incremental
            else:
                result = self._compute_person_embedding_vector(person_id)
                if result is None:
                    # Every visible face lacks a face_search row (Immich-ML hasn't processed them
                    # yet) - nothing to average, so this behaves like the "no faces at all" case
                    # above rather than crashing on a NULL avg() or caching a stale/garbage vector.
                    self._clear_person_cache(person_id)
                    return None
                embedding, embedding_count = result
            self._save_person_embedding(person_id, embedding, current_count, embedding_count, watermark)

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

    def _album_intact_count(self, album_id: UUID, watermark: datetime) -> int:
        """How many of this album's current `album_asset` rows already existed (by `updatedAt`)
        as of `watermark` - the album counterpart of _person_intact_count, same deliberately
        non-eligibility-filtered scope as _album_asset_count/_ALBUM_INTACT_COUNT_QUERY."""
        with self._engine.connect() as conn:
            return conn.execute(
                _ALBUM_INTACT_COUNT_QUERY, {"album_id": str(album_id), "watermark": watermark}
            ).scalar_one()

    def _read_album_cache_row(self, album_id: UUID) -> Row | None:
        with self._app_engine.connect() as conn:
            return conn.execute(
                sa.select(
                    _ALBUM_CACHE_TABLE.c.embedding,
                    _ALBUM_CACHE_TABLE.c.asset_count,
                    _ALBUM_CACHE_TABLE.c.embedding_count,
                    _ALBUM_CACHE_TABLE.c.computed_at,
                ).where(_ALBUM_CACHE_TABLE.c.album_id == album_id)
            ).first()

    def _compute_album_embedding_vector(self, album_id: UUID) -> tuple[list[float], int] | None:
        """The actual CLIP average over Immich's `smart_search` rows, plus how many rows it was
        averaged over (see _ALBUM_AVG_EMBEDDING_QUERY's own comment). None when every asset in the
        album is either ineligible or has no `smart_search` row yet - nothing to average."""
        with self._engine.connect() as conn:
            row = conn.execute(_ALBUM_AVG_EMBEDDING_QUERY, {"album_id": str(album_id)}).one()
        if row.avg_embedding is None:
            return None
        return _parse_vector_text(row.avg_embedding), row.embedding_count

    def _try_incremental_album_update(self, album_id: UUID, cached: Row) -> tuple[list[float], int] | None:
        """Album counterpart of _try_incremental_person_update - see that method's docstring for
        the guard logic, identical here. Doesn't do anything about an asset that became ineligible
        (archived/deleted) without touching album_asset - neither this nor the plain fingerprint
        detects that, same accepted imprecision either way (see the module docstring on
        persistence/album_ml_cache.py); "reprocess all" is still the only fix for it."""
        if cached.embedding_count is None:
            return None
        intact_count = self._album_intact_count(album_id, cached.computed_at)
        if intact_count != cached.embedding_count:
            return None

        with self._engine.connect() as conn:
            new = conn.execute(
                _ALBUM_NEW_AVG_EMBEDDING_QUERY, {"album_id": str(album_id), "watermark": cached.computed_at}
            ).one()
        if new.avg_embedding is None:
            return list(cached.embedding), cached.embedding_count

        new_embedding = _parse_vector_text(new.avg_embedding)
        merged = merge_weighted_average(list(cached.embedding), cached.embedding_count, new_embedding, new.new_count)
        return merged, cached.embedding_count + new.new_count

    def _save_album_embedding(
        self, album_id: UUID, embedding: list[float], asset_count: int, embedding_count: int, computed_at: datetime
    ) -> None:
        with self._app_engine.begin() as conn:
            upsert = pg_insert(_ALBUM_CACHE_TABLE).values(
                album_id=album_id,
                embedding=embedding,
                asset_count=asset_count,
                embedding_count=embedding_count,
                computed_at=computed_at,
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=[_ALBUM_CACHE_TABLE.c.album_id],
                set_={
                    "embedding": upsert.excluded.embedding,
                    "asset_count": upsert.excluded.asset_count,
                    "embedding_count": upsert.excluded.embedding_count,
                    "computed_at": upsert.excluded.computed_at,
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
        the freshness check *and* the incremental path below, and always does a full recompute -
        the admin "reprocess all" path, reached via compute_album_embedding below."""
        current_count = self._album_asset_count(album_id)

        if current_count == 0:
            self._clear_album_cache(album_id)
            return None

        cached = None if force else self._read_album_cache_row(album_id)
        if cached is not None and cached.asset_count == current_count:
            return np.array(cached.embedding, dtype=np.float32)

        watermark = self._watermark()
        incremental = None if cached is None else self._try_incremental_album_update(album_id, cached)
        mode = "incremental" if incremental is not None else "full"

        # INFO, not DEBUG: a recompute (cache miss or stale, or a forced reprocess) is rare and
        # intrinsically interesting on a live instance - a hit is the common case and stays
        # unlogged. `mode` distinguishes the incremental fast path from a full recompute, so it's
        # visible from the logs alone whether the guard is actually paying off in practice.
        with timed(
            "ml.recompute_embedding",
            level=logging.INFO,
            entity="album",
            id=str(album_id),
            asset_count=current_count,
            mode=mode,
        ):
            if incremental is not None:
                embedding, embedding_count = incremental
            else:
                result = self._compute_album_embedding_vector(album_id)
                if result is None:
                    # Every asset in the album is either ineligible (soft-deleted/archived/hidden) or
                    # has no smart_search row yet (e.g. Immich-ML hasn't processed it) - nothing to
                    # average, so this behaves like the "no assets at all" case above rather than
                    # caching a vector.
                    self._clear_album_cache(album_id)
                    return None
                embedding, embedding_count = result
            self._save_album_embedding(album_id, embedding, current_count, embedding_count, watermark)

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
