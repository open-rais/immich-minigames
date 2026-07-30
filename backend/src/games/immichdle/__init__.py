"""Immichdle - see games/immichdle/game.py. Re-exports the public surface so
`from games.immichdle import ImmichdleGame` (external callers, tests) keeps working unchanged."""

from games.immichdle.game import (
    ASSET_COUNT_WEIGHT_EXPONENT,
    GAME_TYPE,
    MODE_PERSON,
    STARTING_SCORE,
    WRONG_GUESS_PENALTY,
    _compute_clues,  # noqa: F401 (re-exported for tests)
    DuplicateGuessError,
    ImmichdleClues,
    ImmichdleGame,
    ImmichdleRound,
    InvalidGuessError,
    PersonSnapshot,
)

__all__ = [
    "ASSET_COUNT_WEIGHT_EXPONENT",
    "GAME_TYPE",
    "MODE_PERSON",
    "STARTING_SCORE",
    "WRONG_GUESS_PENALTY",
    "DuplicateGuessError",
    "ImmichdleClues",
    "ImmichdleGame",
    "ImmichdleRound",
    "InvalidGuessError",
    "PersonSnapshot",
]
