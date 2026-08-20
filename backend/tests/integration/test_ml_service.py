import logging
from uuid import uuid4

import numpy as np
import pytest
import sqlalchemy as sa
from sqlalchemy import text

from persistence.immich_tables import person as person_table
from persistence.ml_cache import EMBEDDING_DIM, AlbumEmbeddingCacheModel, PersonFaceEmbeddingCacheModel
from services.ml_service import _parse_vector_text

_CACHE_TABLE = PersonFaceEmbeddingCacheModel.__table__
_ALBUM_CACHE_TABLE = AlbumEmbeddingCacheModel.__table__

# Same shape as _AVG_EMBEDDING_QUERY (services/ml_service.py) but restricted to faces that existed
# (by updatedAt) at some watermark - used to build a synthetic "cache row as it would have looked
# right after a real computation at that watermark", entirely from real dev data, to exercise the
# incremental path below without writing to Immich's own (read-only) database.
_PERSON_AVG_BEFORE_QUERY = text("""
    SELECT avg(fs.embedding)::text AS avg_embedding, count(*) AS n
    FROM asset_face af
    JOIN face_search fs ON fs."faceId" = af.id
    WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible" AND af."updatedAt" <= :watermark
""")


class TestFaceSimilarity:
    def test_same_person_is_always_one(self, ml_service):
        person_id = uuid4()

        assert ml_service.face_similarity(person_id, person_id) == 1.0

    def test_unknown_person_returns_none(self, ml_service):
        assert ml_service.face_similarity(uuid4(), uuid4()) is None

    def test_two_real_people_returns_a_similarity_in_range_or_none(self, immich_service, ml_service):
        persons = immich_service.get_persons(named_only=True, limit=100)
        with_faces = [p for p in persons if p.asset_count > 0]
        assert len(with_faces) >= 2, "dev data needs at least two named people with faces for this test"

        similarity = ml_service.face_similarity(with_faces[0].id, with_faces[1].id)

        # Cosine similarity is mathematically -1..1, not 0..1 - unrelated faces routinely land
        # slightly negative (see docs/ARCHITECTURE/IMMICH.md's face_search section).
        assert similarity is None or -1.0 <= similarity <= 1.0


# _get_person_embedding is the caching layer behind face_similarity (services/ml_service.py) -
# tested directly here since these scenarios are about the cache's own contract (freshness,
# recompute-on-miss, no-garbage-on-empty), not about face_similarity's already-covered behavior.
class TestPersonEmbeddingCache:
    @staticmethod
    def _pick_person_with_faces(immich_service):
        persons = immich_service.get_persons(named_only=True, limit=100)
        with_faces = [p for p in persons if p.asset_count > 0]
        assert with_faces, "dev data needs at least one named person with faces for this test"
        return with_faces[0]

    @staticmethod
    def _read_cache_row(app_engine, person_id):
        # A fresh Core query against the app engine directly, deliberately not reusing the
        # `db_session` fixture for post-call reads: MLService writes through its own raw
        # connections, and db_session's identity map/expiry state can't be trusted to reflect
        # writes made outside of it.
        with app_engine.connect() as conn:
            return conn.execute(
                sa.select(
                    _CACHE_TABLE.c.embedding,
                    _CACHE_TABLE.c.face_count,
                    _CACHE_TABLE.c.embedding_count,
                    _CACHE_TABLE.c.computed_at,
                ).where(_CACHE_TABLE.c.person_id == person_id)
            ).first()

    def test_cache_miss_computes_and_stores_a_row(self, immich_service, ml_service, db_session, app_engine):
        person = self._pick_person_with_faces(immich_service)
        db_session.execute(sa.delete(_CACHE_TABLE).where(_CACHE_TABLE.c.person_id == person.id))
        db_session.commit()

        embedding = ml_service._get_person_embedding(person.id)

        assert embedding is not None
        assert embedding.shape == (EMBEDDING_DIM,)
        row = self._read_cache_row(app_engine, person.id)
        assert row is not None
        assert row.face_count > 0
        assert list(row.embedding) == pytest.approx(embedding.tolist())

    def test_cache_hit_returns_the_stored_embedding_without_recomputing(
        self, immich_service, ml_service, db_session, app_engine
    ):
        person = self._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)  # warm the cache with a real row
        real_count = self._read_cache_row(app_engine, person.id).face_count

        # Overwrite the cached embedding with an obviously-fake sentinel, keeping face_count
        # matching current reality - if this is returned as-is, the row was actually reused
        # (a real recompute would produce the true average embedding, not this sentinel).
        sentinel = [1.0] * EMBEDDING_DIM
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(embedding=sentinel, face_count=real_count)
        )
        db_session.commit()

        embedding = ml_service._get_person_embedding(person.id)

        assert embedding is not None
        assert embedding.tolist() == pytest.approx(sentinel)

    def test_stale_face_count_triggers_recomputation(self, immich_service, ml_service, db_session, app_engine):
        person = self._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)  # warm the cache, learn the real counts
        real_row = self._read_cache_row(app_engine, person.id)

        sentinel = [1.0] * EMBEDDING_DIM
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(
                embedding=sentinel,
                face_count=real_row.face_count + 1,
                # Also wrong, not just face_count: a mismatched embedding_count is what actually
                # fails the incremental guard (the guard never looks at face_count - see
                # _try_incremental_person_update) and forces the full recompute this test expects.
                # A face_count-only mismatch is what "some new face was added" looks like, which is
                # exactly the case the incremental path exists to shortcut past the sentinel below.
                embedding_count=real_row.embedding_count + 1,
            )
        )
        db_session.commit()

        embedding = ml_service._get_person_embedding(person.id)

        assert embedding is not None
        assert embedding.tolist() != pytest.approx(sentinel)
        row = self._read_cache_row(app_engine, person.id)
        assert row.face_count == real_row.face_count

    def test_person_with_no_faces_returns_none_and_clears_any_cached_row(self, ml_service, db_session, app_engine):
        person_id = uuid4()
        # A stale row for a person who has since lost every face (e.g. all their faces were
        # unassigned in Immich) - must be cleared, not just ignored, so nothing ever reads it as
        # if it were still valid.
        db_session.add(
            PersonFaceEmbeddingCacheModel(
                person_id=person_id, embedding=[0.0] * EMBEDDING_DIM, face_count=5, embedding_count=5
            )
        )
        db_session.commit()

        embedding = ml_service._get_person_embedding(person_id)

        assert embedding is None
        assert self._read_cache_row(app_engine, person_id) is None


# compute_person_embedding/compute_album_embedding are the public entry points the admin
# embedding worker calls - `force=True` is the "reprocess all" path, and has to actually
# recompute even when the cache already looks fresh, unlike a normal cache hit.
class TestForceRecompute:
    def test_force_recomputes_person_embedding_even_when_cache_is_fresh(
        self, immich_service, ml_service, db_session, app_engine
    ):
        person = TestPersonEmbeddingCache._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)  # warm the cache with a real row
        real_count = TestPersonEmbeddingCache._read_cache_row(app_engine, person.id).face_count
        sentinel = [1.0] * EMBEDDING_DIM
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(embedding=sentinel, face_count=real_count)
        )
        db_session.commit()

        embedding = ml_service.compute_person_embedding(person.id, force=True)

        assert embedding is not None
        assert embedding.tolist() != pytest.approx(sentinel)

    def test_without_force_a_fresh_person_cache_is_left_untouched(
        self, immich_service, ml_service, db_session, app_engine
    ):
        person = TestPersonEmbeddingCache._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)
        real_count = TestPersonEmbeddingCache._read_cache_row(app_engine, person.id).face_count
        sentinel = [1.0] * EMBEDDING_DIM
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(embedding=sentinel, face_count=real_count)
        )
        db_session.commit()

        embedding = ml_service.compute_person_embedding(person.id)

        assert embedding.tolist() == pytest.approx(sentinel)


# stale_person_ids/stale_album_ids - the two-query-plus-diff staleness check, exercised against
# real dev data rather than mocks since its whole point is to match get_persons(named_only=True)'s
# own eligibility filter exactly.
class TestStalePersonIds:
    def test_eligible_only_total_matches_get_persons_named_only_universe(self, immich_service, ml_service):
        eligible = immich_service.get_persons(named_only=True, limit=10_000)

        result = ml_service.stale_person_ids(eligible_only=True)

        assert result.total == len(eligible)

    def test_eligible_only_false_returns_the_full_person_universe(self, ml_service, immich_engine):
        with immich_engine.connect() as conn:
            total_persons = conn.execute(sa.select(sa.func.count()).select_from(person_table)).scalar_one()

        result = ml_service.stale_person_ids(eligible_only=False)

        assert result.total == total_persons

    def test_never_cached_person_is_stale(self, immich_service, ml_service, db_session):
        person = TestPersonEmbeddingCache._pick_person_with_faces(immich_service)
        db_session.execute(sa.delete(_CACHE_TABLE).where(_CACHE_TABLE.c.person_id == person.id))
        db_session.commit()

        result = ml_service.stale_person_ids(eligible_only=True)

        assert person.id in result.ids

    def test_freshly_cached_person_is_not_stale(self, immich_service, ml_service):
        person = TestPersonEmbeddingCache._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)  # warm the cache

        result = ml_service.stale_person_ids(eligible_only=True)

        assert person.id not in result.ids

    def test_wrong_cached_face_count_is_stale(self, immich_service, ml_service, db_session, app_engine):
        person = TestPersonEmbeddingCache._pick_person_with_faces(immich_service)
        ml_service._get_person_embedding(person.id)
        real_count = TestPersonEmbeddingCache._read_cache_row(app_engine, person.id).face_count
        db_session.execute(
            sa.update(_CACHE_TABLE).where(_CACHE_TABLE.c.person_id == person.id).values(face_count=real_count + 1)
        )
        db_session.commit()

        result = ml_service.stale_person_ids(eligible_only=True)

        assert person.id in result.ids


class TestStaleAlbumIds:
    @staticmethod
    def _pick_any_album(immich_service):
        albums = immich_service.get_albums(limit=100)
        assert albums, "dev data needs at least one album for this test"
        return albums[0]

    def test_total_matches_get_albums_universe(self, immich_service, ml_service):
        albums = immich_service.get_albums(limit=10_000)

        result = ml_service.stale_album_ids()

        assert result.total == len(albums)

    def test_never_cached_album_is_stale(self, immich_service, ml_service, db_session):
        album = self._pick_any_album(immich_service)
        db_session.execute(sa.delete(_ALBUM_CACHE_TABLE).where(_ALBUM_CACHE_TABLE.c.album_id == album.id))
        db_session.commit()

        result = ml_service.stale_album_ids()

        assert album.id in result.ids

    def test_wrong_cached_asset_count_is_stale(self, immich_service, ml_service, db_session):
        album = self._pick_any_album(immich_service)
        # Doesn't need a real embedding row - the diff only compares asset_count, so a synthetic
        # cache row with a deliberately wrong count is enough to exercise the mismatch path.
        db_session.execute(sa.delete(_ALBUM_CACHE_TABLE).where(_ALBUM_CACHE_TABLE.c.album_id == album.id))
        db_session.execute(
            sa.insert(_ALBUM_CACHE_TABLE).values(
                album_id=album.id, embedding=[0.0] * EMBEDDING_DIM, asset_count=album.asset_count + 1
            )
        )
        db_session.commit()

        result = ml_service.stale_album_ids()

        assert album.id in result.ids


# The critical F4 verification: the incremental path has to produce the *same* vector a full
# recompute would, not just "close enough by eye" - entirely against real dev data, without
# writing to Immich's own database (read-only for this app's DB role). The technique: find a real
# person whose faces span two distinct updatedAt values, compute what a full recompute would have
# produced using only the "old" (earlier) subset - that's exactly what a real cache row would have
# looked like right after being computed at that watermark - write that as the cache row by hand
# (this app's own database *is* writable), then let MLService's normal incremental path pick up
# from there and fold in the "new" (later) subset. The result has to match a real full recompute
# over the complete current set.
class TestIncrementalMatchesFullRecompute:
    @staticmethod
    def _find_person_with_a_real_split_point(immich_service, immich_engine):
        """A named person with at least two distinct face updatedAt values - without that there's
        no real "old vs. new" boundary to test the merge against."""
        for candidate in immich_service.get_persons(named_only=True, limit=200):
            with immich_engine.connect() as conn:
                updated_ats = (
                    conn.execute(
                        text(
                            'SELECT DISTINCT af."updatedAt" FROM asset_face af '
                            'JOIN face_search fs ON fs."faceId" = af.id '
                            'WHERE af."personId" = :person_id AND af."deletedAt" IS NULL AND af."isVisible" '
                            'ORDER BY af."updatedAt"'
                        ),
                        {"person_id": str(candidate.id)},
                    )
                    .scalars()
                    .all()
                )
            if len(updated_ats) >= 2:
                # Midpoint, not the first gap - gives both the "old" and "new" subsets more than
                # one face where the data allows it, closer to a realistic incremental update.
                return candidate, updated_ats[len(updated_ats) // 2]
        return None, None

    def test_incremental_update_matches_a_full_recompute(
        self, immich_service, immich_engine, ml_service, db_session, caplog
    ):
        person, watermark = self._find_person_with_a_real_split_point(immich_service, immich_engine)
        assert person is not None, "dev data needs a named person whose faces span 2+ distinct updatedAt values"

        with immich_engine.connect() as conn:
            old_subset = conn.execute(
                _PERSON_AVG_BEFORE_QUERY, {"person_id": str(person.id), "watermark": watermark}
            ).one()
        assert old_subset.avg_embedding is not None and old_subset.n > 0

        full_embedding = ml_service.compute_person_embedding(person.id, force=True)
        assert full_embedding is not None

        # The cache row as it would look right after a real computation at `watermark`, from only
        # the "old" subset - face_count deliberately left mismatched with reality (irrelevant to
        # the incremental decision itself, see _try_incremental_person_update; only embedding_count
        # + computed_at matter) so the top-level freshness check doesn't short-circuit to a hit.
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(
                embedding=_parse_vector_text(old_subset.avg_embedding),
                embedding_count=old_subset.n,
                face_count=old_subset.n,
                computed_at=watermark,
            )
        )
        db_session.commit()

        caplog.clear()  # drop the force=True call's own "mode=full" line above
        with caplog.at_level(logging.INFO, logger="perf"):
            incremental_embedding = ml_service.compute_person_embedding(person.id, force=False)

        assert incremental_embedding is not None
        assert np.allclose(incremental_embedding, full_embedding, atol=1e-4)
        # Confirms the incremental path was actually taken, not a silent fallback to a full
        # recompute - a fallback would still pass the assertion above (both recompute the same
        # real data over again) and hide the very thing this test exists to check.
        recompute_records = [r for r in caplog.records if getattr(r, "event", None) == "ml.recompute_embedding"]
        assert len(recompute_records) == 1
        assert recompute_records[0].mode == "incremental"
