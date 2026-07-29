"""Roadmap #G (daily games) - MoreOrLess's DailySupport implementation (games/daily.py's
contract): generates a day's shared content, decides which ids future days must avoid repeating,
and builds the kwargs to replay it against the *same* MoreOrLessGame class a normal game uses (see
docs/TODO/DECOUPLING.md decision C)."""

from typing import Any
from uuid import UUID, uuid4

from games.daily import GENERATOR_OWNER
from games.more_or_less.album_assets import AlbumAssetsProvider
from games.more_or_less.game import (
    MODE_PERSON_ASSETS,
    CandidateProvider,
    EntitySnapshot,
    MoreOrLessGame,
)
from games.more_or_less.person_assets import PersonAssetsProvider
from services.immich_service import ImmichService
from services.ml_service import MLService


class ScriptedCandidateProvider(CandidateProvider):
    """Plays back a pre-generated chain (build_spec's "chain" below, built using this same engine)
    instead of sampling from Immich live. `sample()` ignores `exclude_ids` entirely - the chain was
    already built repeat-free (or intentionally allowing a repeat, mirroring the real game's own
    small-pool fallback - see games/more_or_less/game.py's create_next_round) at generation time,
    so re-filtering it here would be redundant. Once the chain is exhausted, `any_exist()` turns
    False, which makes MoreOrLessGame.has_next_round() end the game as "perfect" (decision [F],
    docs/TODO/DAILY-GAMES.md) rather than as a loss."""

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


def build_spec(mode: str, immich_service: ImmichService, settings: dict[str, float]) -> dict[str, Any]:
    # MoreOrLessGame.has_next_round() checks the *previous* round's score_delta (a real guess) -
    # meaningless for a precomputed chain, so this drives create_next_round() directly for a fixed
    # length instead (mirroring the real game's own infinite-chain fallback - see
    # games/more_or_less/game.py's create_next_round, which already tolerates a library smaller
    # than the chain by allowing repeats rather than raising).
    provider_cls = PersonAssetsProvider if mode == MODE_PERSON_ASSETS else AlbumAssetsProvider
    provider = provider_cls(immich_service)
    chain_length = int(settings.get("chain_length", 100))

    game = MoreOrLessGame.start(id=uuid4(), owner=GENERATOR_OWNER, mode=mode, provider=provider)
    chain = [game.rounds[0].reference, game.rounds[0].candidate]
    while len(chain) < chain_length + 1:
        next_round = game.create_next_round()
        chain.append(next_round.candidate)
        game.rounds.append(next_round)
    return {"chain": [entity.to_dict() for entity in chain]}


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    """Decision [F] (docs/TODO/DAILY-GAMES.md) - MoreOrLess never gets cross-day exclusion at all,
    unlike every other game. Always returning the empty set is what keeps
    GamesService._collect_recent_exclusion_ids empty for this game, so the daily generator never
    wraps its immich_service in _ExcludingImmichService. This is the deliberate decision itself,
    not a stub left to "fill in later"."""
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
    # start() consumes chain[0] (reference) + chain[1] (first candidate); each further round played
    # consumes one more - see ScriptedCandidateProvider.
    next_index = rounds_played + 1
    return {"provider": ScriptedCandidateProvider(chain, next_index), "mode": mode, "settings": settings}
