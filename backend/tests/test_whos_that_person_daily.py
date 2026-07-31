"""Roadmap #G, phase F3 - pure unit tests (no DB) for Who'sThatPerson's daily support
(games/whos_that_person/daily.py::ScriptedContent). Hand-constructed content, so none of this
needs the immich_service/db_session fixtures."""

from uuid import uuid4

from games.whos_that_person import HiddenFace, WhosThatPersonGame
from games.whos_that_person.daily import ScriptedContent


def _hidden_face() -> dict:
    return HiddenFace(
        face_id=uuid4(),
        person_id=uuid4(),
        person_name="Person",
        image_width=100,
        image_height=100,
        bounding_box_x1=0,
        bounding_box_y1=0,
        bounding_box_x2=10,
        bounding_box_y2=10,
    ).to_dict()


class TestWhosThatPersonScriptedContent:
    def test_replays_the_spec_rounds_in_order(self):
        rounds_spec = [
            {"asset_id": str(uuid4()), "faces": [_hidden_face()]},
            {"asset_id": str(uuid4()), "faces": [_hidden_face(), _hidden_face()]},
        ]
        game = WhosThatPersonGame.start(
            id=uuid4(),
            immich_service=None,  # type: ignore[arg-type]
            content=ScriptedContent(rounds_spec),
            settings={"total_people": 3, "max_hidden_faces": 5},
        )

        assert len(game.rounds[0].faces) == 1
        assert game.has_next_round() is True

        game.rounds.append(game.create_next_round())
        assert len(game.rounds[1].faces) == 2
        assert game.has_next_round() is False  # total_people (3) reached

    def test_resuming_mid_game_continues_from_the_right_index(self):
        second_asset_id = uuid4()
        rounds_spec = [
            {"asset_id": str(uuid4()), "faces": [_hidden_face()]},
            {"asset_id": str(second_asset_id), "faces": [_hidden_face()]},
        ]
        # Mirrors games/whos_that_person/daily.py's game_kwargs: next_index=rounds_played.
        content = ScriptedContent(rounds_spec, next_index=1)

        picked = content.pick_round(max_faces=5, exclude_asset_ids=frozenset())

        assert picked is not None
        asset_id, _faces = picked
        assert asset_id == second_asset_id
