from uuid import uuid4

import pytest
import sqlalchemy as sa

from persistence.ml_cache import EMBEDDING_DIM, PersonFaceEmbeddingCacheModel

_CACHE_TABLE = PersonFaceEmbeddingCacheModel.__table__


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
                sa.select(_CACHE_TABLE.c.embedding, _CACHE_TABLE.c.face_count).where(
                    _CACHE_TABLE.c.person_id == person_id
                )
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
        ml_service._get_person_embedding(person.id)  # warm the cache, learn the real face_count
        real_count = self._read_cache_row(app_engine, person.id).face_count

        sentinel = [1.0] * EMBEDDING_DIM
        db_session.execute(
            sa.update(_CACHE_TABLE)
            .where(_CACHE_TABLE.c.person_id == person.id)
            .values(embedding=sentinel, face_count=real_count + 1)  # deliberately wrong -> stale
        )
        db_session.commit()

        embedding = ml_service._get_person_embedding(person.id)

        assert embedding is not None
        assert embedding.tolist() != pytest.approx(sentinel)
        row = self._read_cache_row(app_engine, person.id)
        assert row.face_count == real_count

    def test_person_with_no_faces_returns_none_and_clears_any_cached_row(self, ml_service, db_session, app_engine):
        person_id = uuid4()
        # A stale row for a person who has since lost every face (e.g. all their faces were
        # unassigned in Immich) - must be cleared, not just ignored, so nothing ever reads it as
        # if it were still valid.
        db_session.add(
            PersonFaceEmbeddingCacheModel(person_id=person_id, embedding=[0.0] * EMBEDDING_DIM, face_count=5)
        )
        db_session.commit()

        embedding = ml_service._get_person_embedding(person_id)

        assert embedding is None
        assert self._read_cache_row(app_engine, person_id) is None
