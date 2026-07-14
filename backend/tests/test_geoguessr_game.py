from uuid import uuid4

import pytest

from games.geoguessr import (
    DECAY_KM,
    FLAT_SCORE_RADIUS_KM,
    MAX_SCORE,
    TOTAL_ROUNDS,
    AssetSnapshot,
    GeoguessrGame,
    GeoguessrRound,
    LatLng,
    haversine_km,
)


def _guess_near(round_: GeoguessrRound, offset_deg: float = 0.001) -> LatLng:
    return LatLng(latitude=round_.asset.latitude + offset_deg, longitude=round_.asset.longitude + offset_deg)


def _guess_far(round_: GeoguessrRound) -> LatLng:
    # Antipodal-ish point - guaranteed far from any real-world asset location.
    lat = -round_.asset.latitude
    lon = round_.asset.longitude + 180 if round_.asset.longitude < 0 else round_.asset.longitude - 180
    return LatLng(latitude=lat, longitude=lon)


class TestGeoguessrGame:
    def test_has_five_rounds_then_finishes(self, immich_service):
        game = GeoguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        rounds_played = 0
        while not game.finished and rounds_played < TOTAL_ROUNDS + 5:
            game.play_round(_guess_near(game.current_round))
            rounds_played += 1

        assert game.finished is True
        assert len(game.rounds) == TOTAL_ROUNDS
        assert rounds_played == TOTAL_ROUNDS

    def test_a_bad_guess_does_not_end_the_game_early(self, immich_service):
        game = GeoguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        game.play_round(_guess_far(game.current_round))

        assert game.finished is False
        assert len(game.rounds) == 2

    def test_does_not_repeat_a_shown_asset_within_the_same_game(self, immich_service):
        game = GeoguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        shown = [game.current_round.asset.id]

        while not game.finished:
            game.play_round(_guess_near(game.current_round))
            if game.finished:
                break
            new_id = game.current_round.asset.id
            assert new_id not in shown
            shown.append(new_id)

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = GeoguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        while not game.finished:
            game.play_round(_guess_near(game.current_round))

        with pytest.raises(ValueError):
            game.play_round(LatLng(latitude=0, longitude=0))


class TestGeoguessrScoring:
    """Isolated from the DB - constructs rounds directly against known coordinates."""

    def _round_at(self, lat: float, lon: float) -> GeoguessrRound:
        asset = AssetSnapshot(id=uuid4(), latitude=lat, longitude=lon)
        return GeoguessrRound(id=uuid4(), game_id=uuid4(), round_index=1, asset=asset)

    def test_flat_max_score_within_one_km(self):
        round_ = self._round_at(0.0, 0.0)
        # ~0.005 degrees of latitude is well under 1km.
        round_.guess = LatLng(latitude=0.005, longitude=0.0)

        assert round_.distance_km < FLAT_SCORE_RADIUS_KM
        assert round_.calculate_score() == MAX_SCORE

    def test_score_decays_with_distance(self):
        near = self._round_at(0.0, 0.0)
        near.guess = LatLng(latitude=10.0, longitude=0.0)

        far = self._round_at(0.0, 0.0)
        far.guess = LatLng(latitude=80.0, longitude=0.0)

        assert near.calculate_score() > far.calculate_score()

    def test_score_at_the_decay_scale_matches_the_formula(self):
        round_ = self._round_at(0.0, 0.0)
        # 1 degree of latitude is ~111.19 km - walk far enough north to land close to DECAY_KM.
        degrees = DECAY_KM / 111.19
        round_.guess = LatLng(latitude=degrees, longitude=0.0)

        # score = round(MAX_SCORE * exp(-distance_km / DECAY_KM)) ~= MAX_SCORE / e at distance == DECAY_KM
        assert abs(round_.calculate_score() - MAX_SCORE / 2.71828) < 50

    def test_score_floors_at_zero_for_a_far_guess(self):
        round_ = self._round_at(0.0, 0.0)
        round_.guess = LatLng(latitude=0.0, longitude=180.0)  # ~antipodal

        assert round_.calculate_score() == 0


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_km(10.0, 20.0, 10.0, 20.0) == 0.0

    def test_equator_quarter_circle(self):
        # From (0,0) to (0,90) is a quarter of the equator's circumference (~40008km / 4).
        distance = haversine_km(0.0, 0.0, 0.0, 90.0)
        assert abs(distance - 10007.5) < 5
