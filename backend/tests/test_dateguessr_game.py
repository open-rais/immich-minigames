from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from domain.asset import Asset
from games.dateguessr import (
    DECAY_DAYS,
    MAX_SCORE,
    TOTAL_ROUNDS,
    AssetSnapshot,
    DateguessrGame,
    DateguessrRound,
    _pick_asset,
)


def _guess_near(round_: DateguessrRound) -> date:
    return round_.asset.date


def _guess_far(round_: DateguessrRound) -> date:
    return round_.asset.date + timedelta(days=365 * 50)


def _asset(asset_id: UUID | None, file_created_at: datetime) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        type="IMAGE",
        file_created_at=file_created_at,
        original_file_name="test.jpg",
        width=1000,
        height=1000,
        is_favorite=False,
        latitude=None,
        longitude=None,
        city=None,
        state=None,
        country=None,
    )


class _FakeImmichService:
    """Deterministic stand-in for ImmichService.get_assets - used for _pick_asset tests that
    shouldn't depend on the real DB's random sampling. Mirrors test_geoguessr_game.py's own
    _FakeImmichService."""

    def __init__(self, assets: list[Asset]) -> None:
        self._assets = assets

    def get_assets(self, *, exclude_ids: frozenset[UUID] = frozenset(), **kwargs) -> list[Asset]:
        return [a for a in self._assets if a.id not in exclude_ids]


class TestDateguessrGame:
    def test_has_five_rounds_then_finishes(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        rounds_played = 0
        while not game.finished and rounds_played < TOTAL_ROUNDS + 5:
            game.play_round(_guess_near(game.current_round))
            rounds_played += 1

        assert game.finished is True
        assert len(game.rounds) == TOTAL_ROUNDS
        assert rounds_played == TOTAL_ROUNDS

    def test_a_bad_guess_does_not_end_the_game_early(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)

        game.play_round(_guess_far(game.current_round))

        assert game.finished is False
        assert len(game.rounds) == 2

    def test_does_not_repeat_a_shown_asset_within_the_same_game(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        shown = [game.current_round.asset.id]

        while not game.finished:
            game.play_round(_guess_near(game.current_round))
            if game.finished:
                break
            new_id = game.current_round.asset.id
            assert new_id not in shown
            shown.append(new_id)

    def test_playing_an_already_finished_game_raises(self, immich_service):
        game = DateguessrGame.start(id=uuid4(), owner="owner", immich_service=immich_service)
        while not game.finished:
            game.play_round(_guess_near(game.current_round))

        with pytest.raises(ValueError):
            game.play_round(date(2020, 1, 1))


class TestDateguessrScoring:
    """Isolated from the DB - constructs rounds directly against known dates."""

    def _round_at(self, d: date) -> DateguessrRound:
        asset = AssetSnapshot(id=uuid4(), date=d)
        return DateguessrRound(id=uuid4(), game_id=uuid4(), round_index=1, asset=asset)

    def test_exact_day_match_gives_max_score(self):
        round_ = self._round_at(date(2020, 6, 15))
        round_.guess = date(2020, 6, 15)

        assert round_.days_off == 0
        assert round_.calculate_score() == MAX_SCORE

    def test_score_decays_with_days_off(self):
        near = self._round_at(date(2020, 1, 1))
        near.guess = date(2020, 1, 8)

        far = self._round_at(date(2020, 1, 1))
        far.guess = date(2015, 1, 1)

        assert near.calculate_score() > far.calculate_score()

    def test_score_at_the_decay_scale_matches_the_formula(self):
        round_ = self._round_at(date(2020, 1, 1))
        round_.guess = date(2020, 1, 1) + timedelta(days=round(DECAY_DAYS))

        # score = round(MAX_SCORE * exp(-days_off / DECAY_DAYS)) ~= MAX_SCORE / e at days_off == DECAY_DAYS
        assert abs(round_.calculate_score() - MAX_SCORE / 2.71828) < 50

    def test_score_floors_at_zero_for_a_far_guess(self):
        round_ = self._round_at(date(2020, 1, 1))
        round_.guess = date(1900, 1, 1)

        assert round_.calculate_score() == 0


class TestPickAsset:
    def test_prefers_a_candidate_far_from_previous_rounds(self):
        near = _asset(None, datetime(2020, 1, 5, tzinfo=timezone.utc))  # 4 days from 2020-01-01
        far = _asset(None, datetime(2015, 1, 1, tzinfo=timezone.utc))
        service = _FakeImmichService([near, far])

        picked = _pick_asset(service, exclude_ids=frozenset(), previous_dates=[date(2020, 1, 1)])

        assert picked.id == far.id

    def test_falls_back_to_first_candidate_if_none_qualify(self):
        near_a = _asset(None, datetime(2020, 1, 2, tzinfo=timezone.utc))
        near_b = _asset(None, datetime(2020, 1, 3, tzinfo=timezone.utc))
        service = _FakeImmichService([near_a, near_b])

        picked = _pick_asset(service, exclude_ids=frozenset(), previous_dates=[date(2020, 1, 1)])

        assert picked.id == near_a.id

    def test_returns_none_when_no_candidates(self):
        service = _FakeImmichService([])

        assert _pick_asset(service, exclude_ids=frozenset(), previous_dates=[]) is None
