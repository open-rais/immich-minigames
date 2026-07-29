"""Who'sThatPerson - see games/whos_that_person/game.py. Re-exports the public surface so
`from games.whos_that_person import WhosThatPersonGame` (external callers, tests) keeps working
unchanged."""

from games.whos_that_person.game import (
    GAME_TYPE,
    MAX_HIDDEN_FACES,
    MODE_NAMED_FACES,
    TOTAL_PEOPLE,
    HiddenFace,
    IncompleteGuessError,
    LiveContent,
    WhosThatPersonContent,
    WhosThatPersonGame,
    WhosThatPersonRound,
)

__all__ = [
    "GAME_TYPE",
    "MAX_HIDDEN_FACES",
    "MODE_NAMED_FACES",
    "TOTAL_PEOPLE",
    "HiddenFace",
    "IncompleteGuessError",
    "LiveContent",
    "WhosThatPersonContent",
    "WhosThatPersonGame",
    "WhosThatPersonRound",
]
