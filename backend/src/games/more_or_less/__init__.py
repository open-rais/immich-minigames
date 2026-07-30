"""MoreOrLess - see games/more_or_less/game.py. Re-exports the public surface (plus the
per-mode providers from person_assets.py/album_assets.py) so `from games.more_or_less import
MoreOrLessGame` (external callers, tests) keeps working unchanged."""

from games.more_or_less.album_assets import AlbumAssetsProvider
from games.more_or_less.game import (
    _RECENT_EXCLUDE_WINDOW,  # noqa: F401 (re-exported for tests)
    GAME_TYPE,
    MODE_ALBUM_ASSETS,
    MODE_PERSON_ASSETS,
    CandidateProvider,
    EntitySnapshot,
    Guess,
    MoreOrLessGame,
    MoreOrLessRound,
)
from games.more_or_less.person_assets import PersonAssetsProvider

__all__ = [
    "GAME_TYPE",
    "MODE_ALBUM_ASSETS",
    "MODE_PERSON_ASSETS",
    "AlbumAssetsProvider",
    "CandidateProvider",
    "EntitySnapshot",
    "Guess",
    "MoreOrLessGame",
    "MoreOrLessRound",
    "PersonAssetsProvider",
]
