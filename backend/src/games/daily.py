"""Contract-only module (no logic) - roadmap #G (daily games). Each `<game>/daily.py` implements
this Protocol so services/daily_challenge_service.py and services/game_factory.py can generate and
replay a daily challenge for any game without knowing that game's own content/picking logic - see
docs/TODO/DECOUPLING.md §4, Fase 4. Structurally, an implementation is the `<game>/daily.py` module
itself (its three top-level functions), not a class instance - `GameSpec.daily` in
games/registry.py holds the module directly.
"""

from typing import Any, Protocol
from uuid import UUID

from services.immich import ContentQueries, ImmichService
from services.ml_service import MLService


class DailySupport(Protocol):
    @staticmethod
    def build_spec(mode: str, immich_service: ContentQueries, settings: dict[str, float]) -> dict[str, Any]:
        """Generates one day's shared content for this (game_type, mode) by driving a throwaway
        instance of this game's own start()/create_next_round() - the same picking logic (candidate
        sampling, spread/separation, weighted target selection) a normal game already uses, never
        reimplemented here. Raises ValueError if the library doesn't have enough content.
        `immich_service` is typed as ContentQueries (not the full ImmichService) because
        services/daily_challenge_service.py sometimes passes its cross-day exclusion wrapper here
        instead of a real ImmichService."""
        ...

    @staticmethod
    def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
        """Which ids from an already-generated spec should be excluded from a future day's
        challenge of the same (game_type, mode) - only the *answer* content, never decorative
        extras (docs/TODO/DAILY-GAMES.md §4.3)."""
        ...

    @staticmethod
    def game_kwargs(
        mode: str,
        spec: dict[str, Any],
        settings: dict[str, float],
        *,
        rounds_played: int,
        immich_service: ImmichService,
        ml_service: MLService,
    ) -> dict[str, Any]:
        """Constructor/start() kwargs for this game's own class (the *same* class a normal game
        uses - see docs/TODO/DECOUPLING.md decision C), sourcing content from the frozen
        `spec`/`settings` instead of live Immich queries or live admin settings. `rounds_played` is
        how many rounds already exist (0 right before calling .start(), or len(persisted rounds)
        when reconstructing an in-progress game) - only a game whose scripted source needs to
        resume mid-sequence (MoreOrLess's chain, Geoguessr/Dateguessr/WhosThatPerson's rounds_spec
        index) actually uses it."""
        ...
