"""The single point of variation between MoreOrLess modes - person_assets.py's PersonAssetsProvider
samples named people, album_assets.py's AlbumAssetsProvider samples albums, a future date-based
mode would sample something else - games/more_or_less/game.py's MoreOrLessGame never knows which."""

from abc import ABC, abstractmethod
from uuid import UUID

from games.more_or_less.round import EntitySnapshot

# How many random candidates to sample when looking for one whose value doesn't tie the
# reference's. Not required for correctness (a tie always counts as a win either way - see
# games/more_or_less/round.py's MoreOrLessRound.calculate_score) - just to keep most rounds a real
# more/less choice instead of a free pass.
_CANDIDATE_SAMPLE_SIZE = 10


class CandidateProvider(ABC):
    """Supplies the entities a MoreOrLess mode compares. This is the single point of variation
    between modes: person_assets.py's PersonAssetsProvider samples named people, album_assets.py's
    AlbumAssetsProvider samples albums, a future date-based mode would sample something else - the
    game engine below never knows which."""

    @abstractmethod
    def sample(self, *, limit: int, exclude_ids: frozenset[UUID]) -> list[EntitySnapshot]:
        """A random sample of up to `limit` entities (id, name, comparable value), excluding
        `exclude_ids`. May return fewer than `limit` (or none) when the pool is that small."""

    @abstractmethod
    def any_exist(self) -> bool:
        """Whether the pool has at least one entity at all - guards against an empty library. The
        game never ends merely because the *recently shown* ones are excluded (see
        create_next_round's fallback), so this ignores any recent-window exclusion."""


def pick_non_tied_candidate(
    provider: CandidateProvider, reference_value: int | str, exclude_ids: frozenset[UUID]
) -> EntitySnapshot | None:
    candidates = provider.sample(limit=_CANDIDATE_SAMPLE_SIZE, exclude_ids=exclude_ids)
    if not candidates:
        return None
    for candidate in candidates:
        if candidate.value != reference_value:
            return candidate
    return candidates[0]
