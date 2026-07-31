"""Pure unit tests (no DB) for Geoguessr's daily support
(games/geoguessr/daily.py::ScriptedContent). Hand-constructed content, so none of this needs the
immich_service/db_session fixtures."""

from uuid import uuid4

from games.geoguessr import AssetSnapshot, GeoguessrGame
from games.geoguessr.daily import ScriptedContent


def _snapshot(**overrides: object) -> dict:
    defaults: dict[str, object] = {"id": uuid4(), "latitude": 1.0, "longitude": 2.0}
    return AssetSnapshot(**{**defaults, **overrides}).to_dict()  # type: ignore[arg-type]


class TestGeoguessrScriptedContent:
    def test_replays_the_spec_rounds_in_order_then_stops(self):
        rounds_spec = [
            {"main": _snapshot(latitude=1.0, longitude=1.0), "extras": []},
            {"main": _snapshot(latitude=2.0, longitude=2.0), "extras": [_snapshot(latitude=2.01, longitude=2.01)]},
        ]
        game = GeoguessrGame.start(
            id=uuid4(),
            content=ScriptedContent(rounds_spec),
            settings={"total_rounds": 2},
        )

        assert game.rounds[0].asset.latitude == 1.0
        assert game.has_next_round() is True

        game.rounds.append(game.create_next_round())
        assert game.rounds[1].asset.latitude == 2.0
        assert len(game.rounds[1].extras) == 1
        assert game.has_next_round() is False  # total_rounds reached

    def test_resuming_mid_game_continues_from_the_right_index(self):
        rounds_spec = [
            {"main": _snapshot(latitude=1.0, longitude=1.0), "extras": []},
            {"main": _snapshot(latitude=2.0, longitude=2.0), "extras": []},
        ]
        # Mirrors games/geoguessr/daily.py's game_kwargs: next_index=rounds_played.
        content = ScriptedContent(rounds_spec, next_index=1)

        asset = content.pick_asset(exclude_ids=frozenset(), previous_answers=[])

        assert asset is not None
        assert asset.latitude == 2.0
