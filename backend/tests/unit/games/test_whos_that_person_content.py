"""Pure unit tests (no DB) for LiveContent - specifically the "how many faces to hide" sampling
that used to live in services/immich/faces.py::get_random_asset_with_named_faces and was moved
here (docs/TODO's minor-refactors item), since it's a Who'sThatPerson design decision, not a
generic Immich query concern."""

from uuid import uuid4

from domain.face import Face
from games.whos_that_person.content import LiveContent


def _fake_face(asset_id) -> Face:
    return Face(
        id=uuid4(),
        asset_id=asset_id,
        person_id=uuid4(),
        person_name="Someone",
        image_width=100,
        image_height=100,
        bounding_box_x1=0,
        bounding_box_y1=0,
        bounding_box_x2=10,
        bounding_box_y2=10,
    )


class _FakeImmichService:
    """Minimal ContentQueries stand-in - LiveContent only needs get_random_asset_with_named_faces."""

    def __init__(self, faces: list[Face]) -> None:
        self._faces = faces
        self.calls: list[dict] = []

    def get_random_asset_with_named_faces(self, **kwargs):
        self.calls.append(kwargs)
        return self._faces


class TestLiveContentPickRound:
    def test_returns_none_when_no_eligible_asset_exists(self):
        content = LiveContent(_FakeImmichService([]))

        assert content.pick_round(max_faces=5, exclude_asset_ids=frozenset()) is None

    def test_returns_every_face_when_at_or_below_the_cap(self):
        asset_id = uuid4()
        faces = [_fake_face(asset_id) for _ in range(3)]
        content = LiveContent(_FakeImmichService(faces))

        picked_asset_id, hidden_faces = content.pick_round(max_faces=3, exclude_asset_ids=frozenset())

        assert picked_asset_id == asset_id
        assert len(hidden_faces) == 3

    def test_caps_at_max_faces_when_more_are_available(self):
        asset_id = uuid4()
        faces = [_fake_face(asset_id) for _ in range(10)]
        content = LiveContent(_FakeImmichService(faces))

        for _ in range(20):
            _, hidden_faces = content.pick_round(max_faces=1, exclude_asset_ids=frozenset())
            assert 1 <= len(hidden_faces) <= 1

    def test_hides_a_random_amount_between_one_and_max_faces_not_always_the_maximum(self):
        # Repeats the pick many times so a fixed "always exactly max_faces" implementation would
        # be caught - flaky only in the astronomically unlikely case of drawing max_faces every
        # single time.
        asset_id = uuid4()
        faces = [_fake_face(asset_id) for _ in range(10)]
        content = LiveContent(_FakeImmichService(faces))

        counts = {len(content.pick_round(max_faces=5, exclude_asset_ids=frozenset())[1]) for _ in range(50)}

        assert counts != {5}
        assert all(1 <= c <= 5 for c in counts)

    def test_forwards_exclude_asset_ids_to_the_immich_service(self):
        service = _FakeImmichService([_fake_face(uuid4())])
        content = LiveContent(service)
        excluded = frozenset({uuid4()})

        content.pick_round(max_faces=5, exclude_asset_ids=excluded)

        assert service.calls[0]["exclude_asset_ids"] == excluded
