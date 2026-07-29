"""Roadmap #G, phase F3 - pure unit tests (no DB) for the scripted-replay classes: games/more_or_
less.py's ScriptedCandidateProvider, games/daily_scripted.py's Daily*Game subclasses, and games/
immichdle.py's target-parameterized ImmichdleGame.start(). All content here is hand-constructed
rather than sampled from Immich, so none of this needs the immich_service/db_session fixtures."""

from datetime import date
from uuid import uuid4

from games.dateguessr import AssetSnapshot as DateguessrAssetSnapshot
from games.daily_scripted import DailyDateguessrGame, DailyGeoguessrGame, DailyWhosThatPersonGame
from games.geoguessr import AssetSnapshot as GeoguessrAssetSnapshot
from games.immichdle import ImmichdleGame, PersonSnapshot
from games.more_or_less import MODE_PERSON_ASSETS, EntitySnapshot, MoreOrLessGame, ScriptedCandidateProvider
from games.whos_that_person import HiddenFace


def _entity(value: int) -> EntitySnapshot:
    return EntitySnapshot(id=uuid4(), name=f"entity-{value}", value=value)


class TestScriptedCandidateProvider:
    def test_start_consumes_chain_0_and_1(self):
        chain = [_entity(1), _entity(2), _entity(3), _entity(4)]
        provider = ScriptedCandidateProvider(chain, next_index=0)

        game = MoreOrLessGame.start(id=uuid4(), owner="owner", mode=MODE_PERSON_ASSETS, provider=provider)

        assert game.rounds[0].reference == chain[0]
        assert game.rounds[0].candidate == chain[1]

    def test_ends_as_finished_once_the_chain_is_exhausted(self):
        # 2 entities: start() consumes both (index 0 as reference, index 1 as candidate) - nothing
        # left at all, so even a correct guess must end the game (decision [F]).
        chain = [_entity(1), _entity(2)]
        provider = ScriptedCandidateProvider(chain, next_index=0)
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", mode=MODE_PERSON_ASSETS, provider=provider)
        first_round = game.current_round
        guess = "more" if first_round.candidate.value > first_round.reference.value else "less"

        result = game.play_round(guess)

        assert result.finished is True
        assert result.score_delta == 1  # ended because the chain ran out, not a loss

    def test_continues_when_the_chain_has_more_left(self):
        chain = [_entity(1), _entity(2), _entity(3), _entity(4)]
        provider = ScriptedCandidateProvider(chain, next_index=0)
        game = MoreOrLessGame.start(id=uuid4(), owner="owner", mode=MODE_PERSON_ASSETS, provider=provider)
        first_round = game.current_round
        guess = "more" if first_round.candidate.value > first_round.reference.value else "less"

        result = game.play_round(guess)

        assert result.finished is False
        assert game.rounds[1].candidate == chain[2]

    def test_resuming_mid_chain_continues_from_the_right_index(self):
        chain = [_entity(1), _entity(2), _entity(3), _entity(4), _entity(5)]
        # Mirrors GamesService._daily_game_kwargs's derivation after 1 round already exists:
        # next_index = rounds_played (1) + 1 = 2.
        provider = ScriptedCandidateProvider(chain, next_index=2)

        assert provider.sample(limit=1, exclude_ids=frozenset()) == [chain[2]]

    def test_any_exist_reflects_remaining_chain(self):
        chain = [_entity(1), _entity(2)]
        assert ScriptedCandidateProvider(chain, next_index=1).any_exist() is True
        assert ScriptedCandidateProvider(chain, next_index=2).any_exist() is False


class TestImmichdleGameWithTarget:
    def test_uses_the_given_target_without_sampling(self):
        target = PersonSnapshot(
            id=uuid4(), name="Target Person", asset_count=10, birth_date=None, first_asset_date=None
        )

        game = ImmichdleGame.start(id=uuid4(), owner="owner", immich_service=None, target=target)  # type: ignore[arg-type]

        assert game.target == target
        assert len(game.rounds) == 1


def _geo_snapshot(**overrides: object) -> dict:
    defaults: dict[str, object] = {"id": uuid4(), "latitude": 1.0, "longitude": 2.0}
    return GeoguessrAssetSnapshot(**{**defaults, **overrides}).to_dict()  # type: ignore[arg-type]


class TestDailyGeoguessrGame:
    def test_replays_the_spec_rounds_in_order_then_stops(self):
        rounds_spec = [
            {"main": _geo_snapshot(latitude=1.0, longitude=1.0), "extras": []},
            {"main": _geo_snapshot(latitude=2.0, longitude=2.0), "extras": [_geo_snapshot(latitude=2.01, longitude=2.01)]},
        ]
        game = DailyGeoguessrGame.start(
            id=uuid4(), owner="owner", immich_service=None, settings={"total_rounds": 2}, rounds_spec=rounds_spec
        )

        assert game.rounds[0].asset.latitude == 1.0
        assert game.has_next_round() is True

        game.rounds.append(game.create_next_round())
        assert game.rounds[1].asset.latitude == 2.0
        assert len(game.rounds[1].extras) == 1
        assert game.has_next_round() is False  # total_rounds reached


def _date_snapshot(**overrides: object) -> dict:
    defaults: dict[str, object] = {"id": uuid4(), "date": date(2020, 1, 1)}
    return DateguessrAssetSnapshot(**{**defaults, **overrides}).to_dict()  # type: ignore[arg-type]


class TestDailyDateguessrGame:
    def test_replays_the_spec_rounds_in_order(self):
        rounds_spec = [
            {"main": _date_snapshot(date=date(2020, 1, 1)), "extras": []},
            {"main": _date_snapshot(date=date(2021, 6, 15)), "extras": []},
        ]
        game = DailyDateguessrGame.start(
            id=uuid4(), owner="owner", immich_service=None, settings={"total_rounds": 2}, rounds_spec=rounds_spec
        )

        assert game.rounds[0].asset.date == date(2020, 1, 1)
        game.rounds.append(game.create_next_round())
        assert game.rounds[1].asset.date == date(2021, 6, 15)
        assert game.has_next_round() is False


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


class TestDailyWhosThatPersonGame:
    def test_replays_the_spec_rounds_in_order(self):
        rounds_spec = [
            {"asset_id": str(uuid4()), "faces": [_hidden_face()]},
            {"asset_id": str(uuid4()), "faces": [_hidden_face(), _hidden_face()]},
        ]
        game = DailyWhosThatPersonGame.start(
            id=uuid4(),
            owner="owner",
            immich_service=None,
            settings={"total_people": 3, "max_hidden_faces": 5},
            rounds_spec=rounds_spec,
        )

        assert len(game.rounds[0].faces) == 1
        assert game.has_next_round() is True

        game.current_round.ending_streak = 0  # normally set by calculate_score() during real play
        game.rounds.append(game.create_next_round())
        assert len(game.rounds[1].faces) == 2
        assert game.has_next_round() is False  # total_people (3) reached
