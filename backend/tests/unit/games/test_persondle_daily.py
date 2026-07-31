"""Pure unit test (no DB) for Persondle's daily support. Persondle needs no content seam of its
own (games/immichdle/daily.py's docstring explains why) - PersondleGame.start() already accepts a
pre-picked `target`, which this covers directly."""

from uuid import uuid4

from games.immichdle import PersondleGame, PersonSnapshot


class TestPersondleGameWithTarget:
    def test_uses_the_given_target_without_sampling(self):
        target = PersonSnapshot(
            id=uuid4(), name="Target Person", asset_count=10, birth_date=None, first_asset_date=None
        )

        game = PersondleGame.start(id=uuid4(), immich_service=None, target=target)  # type: ignore[arg-type]

        assert game.target == target
        assert len(game.rounds) == 1
