"""Roadmap #G, phase F3 - pure unit tests (no DB) for MoreOrLess's daily support
(games/more_or_less/daily.py::ScriptedCandidateProvider). Hand-constructed content, so none of
this needs the immich_service/db_session fixtures."""

from uuid import uuid4

from games.more_or_less import MODE_PERSON_ASSETS, EntitySnapshot, MoreOrLessGame
from games.more_or_less.daily import ScriptedCandidateProvider


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
        # Mirrors more_or_less/daily.py's game_kwargs derivation after 1 round already exists:
        # next_index = rounds_played (1) + 1 = 2.
        provider = ScriptedCandidateProvider(chain, next_index=2)

        assert provider.sample(limit=1, exclude_ids=frozenset()) == [chain[2]]

    def test_any_exist_reflects_remaining_chain(self):
        chain = [_entity(1), _entity(2)]
        assert ScriptedCandidateProvider(chain, next_index=1).any_exist() is True
        assert ScriptedCandidateProvider(chain, next_index=2).any_exist() is False
