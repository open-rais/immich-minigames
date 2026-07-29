"""Roadmap #G, phase F3 - pure unit tests (no DB) for Dateguessr's daily support
(games/dateguessr/daily.py::ScriptedContent). Hand-constructed content, so none of this needs the
immich_service/db_session fixtures."""

from datetime import date
from uuid import uuid4

from games.dateguessr import AssetSnapshot, DateguessrGame
from games.dateguessr.daily import ScriptedContent


def _snapshot(**overrides: object) -> dict:
    defaults: dict[str, object] = {"id": uuid4(), "date": date(2020, 1, 1)}
    return AssetSnapshot(**{**defaults, **overrides}).to_dict()  # type: ignore[arg-type]


class TestDateguessrScriptedContent:
    def test_replays_the_spec_rounds_in_order(self):
        rounds_spec = [
            {"main": _snapshot(date=date(2020, 1, 1)), "extras": []},
            {"main": _snapshot(date=date(2021, 6, 15)), "extras": []},
        ]
        game = DateguessrGame.start(
            id=uuid4(),
            owner="owner",
            content=ScriptedContent(rounds_spec),
            settings={"total_rounds": 2},
        )

        assert game.rounds[0].asset.date == date(2020, 1, 1)
        game.rounds.append(game.create_next_round())
        assert game.rounds[1].asset.date == date(2021, 6, 15)
        assert game.has_next_round() is False

    def test_resuming_mid_game_continues_from_the_right_index(self):
        rounds_spec = [
            {"main": _snapshot(date=date(2020, 1, 1)), "extras": []},
            {"main": _snapshot(date=date(2021, 6, 15)), "extras": []},
        ]
        # Mirrors games/dateguessr/daily.py's game_kwargs: next_index=rounds_played.
        content = ScriptedContent(rounds_spec, next_index=1)

        asset = content.pick_asset(exclude_ids=frozenset(), previous_answers=[])

        assert asset is not None
        assert asset.local_date == date(2021, 6, 15)
