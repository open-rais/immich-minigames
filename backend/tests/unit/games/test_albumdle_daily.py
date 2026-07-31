"""Pure unit test (no DB) for Albumdle's daily support. Albumdle needs no content seam of its own
(games/immichdle/daily.py's docstring explains why) - AlbumdleGame.start() already accepts a
pre-picked `target`, which this covers directly. Mirrors test_persondle_daily.py."""

from uuid import uuid4

from games.immichdle import AlbumdleGame, AlbumSnapshot


class TestAlbumdleGameWithTarget:
    def test_uses_the_given_target_without_sampling(self):
        target = AlbumSnapshot(
            id=uuid4(),
            name="Target Album",
            asset_count=10,
            first_asset_date=None,
            dominant_person_ids=(),
            dominant_person_name=None,
            unique_named_person_count=0,
        )

        game = AlbumdleGame.start(id=uuid4(), immich_service=None, target=target)  # type: ignore[arg-type]

        assert game.target == target
        assert len(game.rounds) == 1
