"""Immichdle - see games/immichdle/game.py for the shared engine, persondle.py/albumdle.py for
each mode's own implementation. Re-exports the public surface so `from games.immichdle import
PersondleGame` (external callers, tests) reads the same as before the package split."""

from games.immichdle.albumdle import AlbumClues, AlbumdleGame, AlbumdleRound, AlbumSnapshot, _compute_album_clues
from games.immichdle.game import (
    GAME_TYPE,
    MODE_ALBUM,
    MODE_PERSON,
    STARTING_SCORE,
    WRONG_GUESS_PENALTY,
    BaseImmichdleGame,
    BaseImmichdleRound,
    DuplicateGuessError,
    InvalidGuessError,
)
from games.immichdle.persondle import (
    ASSET_COUNT_WEIGHT_EXPONENT,
    PersonClues,
    PersondleGame,
    PersondleRound,
    PersonSnapshot,
    _compute_person_clues,
)

__all__ = [
    "ASSET_COUNT_WEIGHT_EXPONENT",
    "GAME_TYPE",
    "MODE_ALBUM",
    "MODE_PERSON",
    "STARTING_SCORE",
    "WRONG_GUESS_PENALTY",
    "AlbumClues",
    "AlbumSnapshot",
    "AlbumdleGame",
    "AlbumdleRound",
    "BaseImmichdleGame",
    "BaseImmichdleRound",
    "DuplicateGuessError",
    "InvalidGuessError",
    "PersonClues",
    "PersonSnapshot",
    "PersondleGame",
    "PersondleRound",
    "_compute_album_clues",
    "_compute_person_clues",
]
