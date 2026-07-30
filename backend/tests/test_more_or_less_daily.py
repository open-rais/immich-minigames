"""Roadmap #G, phase F3 - pure unit tests (no DB) for MoreOrLess's daily support
(games/more_or_less/daily.py::ScriptedCandidateProvider, _BufferedProvider). Hand-constructed
content, so none of this needs the immich_service/db_session fixtures."""

from uuid import UUID, uuid4

from games.more_or_less import MODE_PERSON_ASSETS, CandidateProvider, EntitySnapshot, MoreOrLessGame
from games.more_or_less.daily import ScriptedCandidateProvider, _BufferedProvider


def _entity(value: int) -> EntitySnapshot:
    return EntitySnapshot(id=uuid4(), name=f"entity-{value}", value=value)


class _FakePool(CandidateProvider):
    """A CandidateProvider over a fixed in-memory pool, counting real sample() calls the way a
    live provider's DB query would count - what _BufferedProvider is meant to shield against."""

    def __init__(self, pool: list[EntitySnapshot]) -> None:
        self._pool = pool
        self.calls = 0

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        self.calls += 1
        eligible = [e for e in self._pool if e.id not in exclude_ids]
        return eligible[:limit]

    def any_exist(self) -> bool:
        return bool(self._pool)


class TestBufferedProvider:
    def test_serves_many_small_samples_from_one_underlying_call(self):
        pool = [_entity(i) for i in range(50)]
        fake = _FakePool(pool)
        buffered = _BufferedProvider(fake, batch_size=50)

        served = [e for _ in range(5) for e in buffered.sample(limit=10, exclude_ids=frozenset())]

        assert len(served) == 50
        assert {e.id for e in served} == {e.id for e in pool}
        assert fake.calls == 1

    def test_repeats_once_the_real_pool_is_exhausted(self):
        # Mirrors create_next_round's own small-pool fallback (repeats allowed once the pool runs
        # dry) - just served from memory instead of a fresh query discovering it every round.
        pool = [_entity(i) for i in range(3)]
        fake = _FakePool(pool)
        buffered = _BufferedProvider(fake, batch_size=10)

        served = [e for _ in range(20) for e in buffered.sample(limit=1, exclude_ids=frozenset())]

        assert len(served) == 20
        assert {e.id for e in served} == {e.id for e in pool}  # only ever these 3, repeated
        assert fake.calls == 2  # 1 to fetch the pool, 1 more to discover it's exhausted

    def test_any_exist_true_even_after_the_buffer_drains(self):
        fake = _FakePool([_entity(1)])
        buffered = _BufferedProvider(fake, batch_size=10)
        buffered.sample(limit=1, exclude_ids=frozenset())

        assert buffered.any_exist() is True

    def test_any_exist_false_for_an_empty_pool(self):
        buffered = _BufferedProvider(_FakePool([]), batch_size=10)

        assert buffered.any_exist() is False


class TestScriptedCandidateProvider:
    def test_start_consumes_chain_0_and_1(self):
        chain = [_entity(1), _entity(2), _entity(3), _entity(4)]
        provider = ScriptedCandidateProvider(chain, next_index=0)

        game = MoreOrLessGame.start(id=uuid4(), mode=MODE_PERSON_ASSETS, provider=provider)

        assert game.rounds[0].reference == chain[0]
        assert game.rounds[0].candidate == chain[1]

    def test_ends_as_finished_once_the_chain_is_exhausted(self):
        # 2 entities: start() consumes both (index 0 as reference, index 1 as candidate) - nothing
        # left at all, so even a correct guess must end the game (decision [F]).
        chain = [_entity(1), _entity(2)]
        provider = ScriptedCandidateProvider(chain, next_index=0)
        game = MoreOrLessGame.start(id=uuid4(), mode=MODE_PERSON_ASSETS, provider=provider)
        first_round = game.current_round
        guess = "more" if first_round.candidate.value > first_round.reference.value else "less"

        result = game.play_round(guess)

        assert result.finished is True
        assert result.score_delta == 1  # ended because the chain ran out, not a loss

    def test_continues_when_the_chain_has_more_left(self):
        chain = [_entity(1), _entity(2), _entity(3), _entity(4)]
        provider = ScriptedCandidateProvider(chain, next_index=0)
        game = MoreOrLessGame.start(id=uuid4(), mode=MODE_PERSON_ASSETS, provider=provider)
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
