"""Pure unit tests (no DB) for Timeline's daily support
(games/timeline/daily.py::ScriptedContent/exclusion_ids). Hand-constructed content, so none of this
needs the immich_service/db_session fixtures - see tests/unit/services/test_daily_challenge_service.py's
TestSpecShapePerGame/TestExclusionWindow for the integration-level coverage (build_spec's actual
shape, two players/days sharing or excluding content) that does need those."""

from datetime import date
from uuid import uuid4

from games.timeline import CardSnapshot, TimelineGame
from games.timeline.daily import ScriptedContent, exclusion_ids


def _snapshot(**overrides: object) -> dict:
    defaults: dict[str, object] = {"id": uuid4(), "date": date(2020, 1, 1)}
    return CardSnapshot(**{**defaults, **overrides}).to_dict()  # type: ignore[arg-type]


class TestTimelineScriptedContent:
    def test_start_consumes_the_seed_and_first_card(self):
        cards = [
            CardSnapshot(uuid4(), date(2020, 1, 1)),
            CardSnapshot(uuid4(), date(2021, 6, 15)),
            CardSnapshot(uuid4(), date(2022, 3, 3)),
        ]
        game = TimelineGame.start(id=uuid4(), content=ScriptedContent(cards, next_index=0), settings={})

        assert game.rounds[0].board == [cards[0]]
        assert game.rounds[0].card == cards[1]

    def test_replays_the_rest_of_the_chain_in_order(self):
        cards = [
            CardSnapshot(uuid4(), date(2020, 1, 1)),
            CardSnapshot(uuid4(), date(2021, 6, 15)),
            CardSnapshot(uuid4(), date(2022, 3, 3)),
        ]
        game = TimelineGame.start(id=uuid4(), content=ScriptedContent(cards, next_index=0), settings={})
        first_round = game.current_round
        first_round.guess = first_round.correct_slot  # always accepted, whatever the tolerance

        result = game.play_round(first_round.correct_slot)

        assert result.finished is False
        assert game.current_round.card == cards[2]

    def test_resuming_mid_chain_continues_from_the_right_index(self):
        cards = [
            CardSnapshot(uuid4(), date(2020, 1, 1)),
            CardSnapshot(uuid4(), date(2021, 6, 15)),
            CardSnapshot(uuid4(), date(2022, 3, 3)),
            CardSnapshot(uuid4(), date(2023, 9, 9)),
        ]
        # Mirrors games/timeline/daily.py's game_kwargs after 1 round already exists:
        # next_index = rounds_played (1) + 1 = 2.
        content = ScriptedContent(cards, next_index=2)

        asset = content.pick_card(exclude_ids=frozenset(), board_dates=[], min_separation_days=30)

        assert asset is not None
        assert asset.local_date == cards[2].date

    def test_ends_as_a_perfect_run_once_the_chain_is_exhausted(self):
        # Only 2 cards: start() consumes both (index 0 as the seed, index 1 as the first card to
        # place) - nothing left at all, so even a correct guess must end the game as a perfect run,
        # not a loss.
        same_day = date(2020, 1, 1)
        cards = [CardSnapshot(uuid4(), same_day), CardSnapshot(uuid4(), same_day)]
        game = TimelineGame.start(id=uuid4(), content=ScriptedContent(cards, next_index=0), settings={})

        result = game.play_round(0)  # both slots are always accepted when dates tie

        assert result.finished is True
        assert result.score_delta == 1  # ended because the chain ran out, not a wrong guess

    def test_has_more_reflects_the_remaining_chain(self):
        cards = [CardSnapshot(uuid4(), date(2020, 1, 1)), CardSnapshot(uuid4(), date(2021, 1, 1))]
        assert ScriptedContent(cards, next_index=1).has_more(frozenset()) is True
        assert ScriptedContent(cards, next_index=2).has_more(frozenset()) is False


class TestExclusionIds:
    def test_returns_every_card_in_the_spec(self):
        spec = {"cards": [_snapshot(), _snapshot(), _snapshot()]}

        ids = exclusion_ids(spec)

        assert len(ids) == 3
        assert {str(i) for i in ids} == {card["id"] for card in spec["cards"]}
