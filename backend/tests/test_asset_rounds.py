"""
Pure-logic tests for the shared fixed-rounds game skeleton (games/asset_rounds.py). No DB - the
candidate-picking and scoring helpers are pure functions. Each concrete game's own metric/snapshot
is covered in test_geoguessr_game.py / test_dateguessr_game.py.
"""

from games.asset_rounds import exp_decay_score, pick_spread_asset


class _Item:
    """Minimal duck-typed stand-in - pick_spread_asset never inspects the candidate itself, it only
    passes it through to the `separation` callback, so a real Asset isn't needed here."""

    def __init__(self, tag: int) -> None:
        self.tag = tag


def _separation(item: _Item, answer: int) -> float:
    return abs(item.tag - answer)


class TestPickSpreadAsset:
    def test_prefers_first_candidate_far_enough_from_every_previous_answer(self):
        near = _Item(1)
        far = _Item(100)

        picked = pick_spread_asset([near, far], previous_answers=[0], separation=_separation, min_separation=50)

        assert picked is far

    def test_falls_back_to_first_candidate_when_none_qualify(self):
        first = _Item(1)
        second = _Item(2)

        picked = pick_spread_asset([first, second], previous_answers=[0], separation=_separation, min_separation=50)

        assert picked is first

    def test_takes_first_candidate_when_there_are_no_previous_answers(self):
        first = _Item(1)
        second = _Item(2)

        picked = pick_spread_asset([first, second], previous_answers=[], separation=_separation, min_separation=50)

        assert picked is first

    def test_returns_none_when_there_are_no_candidates(self):
        assert pick_spread_asset([], previous_answers=[], separation=_separation, min_separation=50) is None


class TestExpDecayScore:
    def test_flat_zone_gives_max_score(self):
        assert exp_decay_score(0.0, flat_zone=1.0, decay=100.0, max_score=5000) == 5000
        assert exp_decay_score(1.0, flat_zone=1.0, decay=100.0, max_score=5000) == 5000

    def test_score_decays_beyond_the_flat_zone(self):
        assert exp_decay_score(200.0, 1.0, 100.0, 5000) < exp_decay_score(50.0, 1.0, 100.0, 5000)

    def test_score_at_one_decay_scale_is_about_max_over_e(self):
        # score = round(max_score * exp(-distance / decay)) ~= max_score / e at distance == decay
        assert abs(exp_decay_score(100.0, 0.0, 100.0, 5000) - 5000 / 2.71828) < 50

    def test_score_floors_at_zero_for_a_far_distance(self):
        assert exp_decay_score(100_000.0, 0.0, 100.0, 5000) == 0
