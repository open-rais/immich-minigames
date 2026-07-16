from uuid import uuid4


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

        assert similarity is None or 0.0 <= similarity <= 1.0
