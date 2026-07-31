"""MoreOrLess's DailySupport implementation (games/daily.py's contract): generates a day's shared
content, decides which ids future days must avoid repeating, and builds the kwargs to replay it
against the *same* MoreOrLessGame class a normal game uses."""

from typing import Any
from uuid import UUID, uuid4

from games.more_or_less.album_assets import AlbumAssetsProvider
from games.more_or_less.content import CandidateProvider
from games.more_or_less.game import MODE_PERSON_ASSETS, MoreOrLessGame
from games.more_or_less.person_assets import PersonAssetsProvider
from games.more_or_less.round import EntitySnapshot
from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService


class _BufferedProvider(CandidateProvider):
    """Wraps a live CandidateProvider with an in-memory buffer, so build_spec's ~chain_length
    create_next_round() calls (each one a sample() call) don't each cost a fresh ORDER BY random()
    scan. Keeps its own running copy of every distinct entity seen (`_pool`): once a query comes
    back with nothing new, the pool is treated as exhausted and every later refill is served by
    re-filtering that copy in memory - the same "repeats are fine once the pool runs out" tolerance
    create_next_round already has for a live game, just without re-querying to discover it every
    time. In practice this means 1 query while the pool has enough unseen entities, and one more to
    detect exhaustion if it doesn't - never one per round."""

    def __init__(self, inner: CandidateProvider, batch_size: int) -> None:
        self._inner = inner
        self._batch_size = batch_size
        self._pool: list[EntitySnapshot] = []
        self._pool_ids: frozenset[UUID] = frozenset()
        self._buffer: list[EntitySnapshot] = []
        self._exhausted = False

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        self._buffer = [e for e in self._buffer if e.id not in exclude_ids]
        if len(self._buffer) < limit and not self._exhausted:
            fresh = self._inner.sample(limit=self._batch_size, exclude_ids=self._pool_ids | exclude_ids)
            if fresh:
                self._pool.extend(fresh)
                self._pool_ids |= {e.id for e in fresh}
                self._buffer.extend(fresh)
            else:
                self._exhausted = True
        if len(self._buffer) < limit and self._exhausted:
            self._buffer.extend(e for e in self._pool if e.id not in exclude_ids)
        result, self._buffer = self._buffer[:limit], self._buffer[limit:]
        return result

    def any_exist(self) -> bool:
        return bool(self._buffer) or bool(self._pool) or self._inner.any_exist()


class ScriptedCandidateProvider(CandidateProvider):
    """Plays back a pre-generated chain (build_spec's "chain" below, built using this same engine)
    instead of sampling from Immich live. `sample()` ignores `exclude_ids` entirely - the chain was
    already built repeat-free (or intentionally allowing a repeat, mirroring the real game's own
    small-pool fallback - see games/more_or_less/game.py's create_next_round) at generation time,
    so re-filtering it here would be redundant. Once the chain is exhausted, `any_exist()` turns
    False, which makes MoreOrLessGame.has_next_round() end the game as "perfect" rather than as a
    loss."""

    def __init__(self, chain: list[EntitySnapshot], next_index: int) -> None:
        self._chain = chain
        self._next_index = next_index

    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        if self._next_index >= len(self._chain):
            return []
        entity = self._chain[self._next_index]
        self._next_index += 1
        return [entity]

    def any_exist(self) -> bool:
        return self._next_index < len(self._chain)


def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
    # MoreOrLessGame.has_next_round() checks the *previous* round's score_delta (a real guess) -
    # meaningless for a precomputed chain, so this drives create_next_round() directly for a fixed
    # length instead (mirroring the real game's own infinite-chain fallback - see
    # games/more_or_less/game.py's create_next_round, which already tolerates a library smaller
    # than the chain by allowing repeats rather than raising).
    provider_cls = PersonAssetsProvider if mode == MODE_PERSON_ASSETS else AlbumAssetsProvider
    chain_length = int(settings.get("chain_length", 100))
    # Batch size generous enough that the whole chain usually comes from one fetch, even accounting
    # for _pick_non_tied_candidate's 10-per-round sample and its small-pool retry - see
    # _BufferedProvider.
    provider = _BufferedProvider(provider_cls(immich_service), batch_size=max(200, (chain_length + 1) * 20))

    game = MoreOrLessGame.start(id=uuid4(), mode=mode, provider=provider)
    chain = [game.rounds[0].reference, game.rounds[0].candidate]
    while len(chain) < chain_length + 1:
        next_round = game.create_next_round()
        chain.append(next_round.candidate)
        game.rounds.append(next_round)
    return {"chain": [entity.to_dict() for entity in chain]}


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    """MoreOrLess never gets cross-day exclusion at all, unlike every other game. Always returning
    the empty set is what keeps GamesService._collect_recent_exclusion_ids empty for this game, so
    the daily generator never wraps its immich_service in _ExcludingImmichService. This is the
    deliberate design itself, not a stub left to "fill in later"."""
    return set()


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    chain = [EntitySnapshot.from_dict(e) for e in spec["chain"]]
    # start() consumes chain[0] (reference) *and* chain[1] (first candidate) in one shot - the only
    # round that draws two entries at once, since every later round only needs one new candidate
    # (its reference is just the previous round's candidate, already known). So the "next fresh
    # index" jumps from 0 straight to 2 after round 1, not 1 - rounds_played + 1 only holds once at
    # least one round has actually been played (rounds_played >= 1); before that (starting fresh),
    # it must be 0, or start() would skip chain[0] and re-draw chain[1] as if it were still fresh -
    # the round that was actually shown becomes a false "tie" against itself.
    next_index = rounds_played + 1 if rounds_played > 0 else 0
    return {"provider": ScriptedCandidateProvider(chain, next_index), "mode": mode, "settings": settings}
