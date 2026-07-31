"""Service-layer exceptions shared by more than one services/*.py module - kept in their own
module (rather than living in whichever service defined them first) specifically to avoid a
circular import: services/games_service.py's GamesService.create_daily_game delegates challenge
generation to services/daily_service.py's DailyService, which needs to raise the very same
NotEnoughContentError games_service.py already defined for its own games' start() failures.

Also holds every game-lifecycle exception games_service.py raises (GameNotFoundError and friends
below) - moved here from games_service.py itself so api/error_handlers.py's exception->status table
can import them without importing games_service.py (which would pull in GamesService's own
dependencies just to read a table of exception types). games_service.py re-imports and re-exports
them, so every existing `from services.games_service import GameNotFoundError` call site (tests)
keeps working unchanged."""


class UnsupportedGameError(Exception):
    pass


class NotEnoughContentError(Exception):
    """Raised when the Immich library doesn't have enough named people/faces/located assets to
    start a game - the friendly ValueError each game's start() already raises for that case (see
    games/more_or_less/game.py, games/immichdle/game.py, games/whos_that_person/game.py,
    games/geoguessr/game.py, games/dateguessr/game.py), re-raised here so main.py can map it to a
    422 instead of it reaching the client as a bare 500. Also raised by services/daily_service.py
    when a daily challenge can't be generated at all."""


class GameNotFoundError(Exception):
    pass


class GameOwnershipError(Exception):
    pass


class RoundNotPendingError(Exception):
    pass


class DailyNotEnabledError(Exception):
    """Roadmap #G - raised by create_daily_game when the (game_type, mode) isn't in today's daily
    rotation (either genuinely unsupported, or a real mode the admin hasn't enabled) - main.py maps
    this to a 404, matching docs/TODO/DAILY-GAMES.md §4.6."""


class DailyAlreadyPlayedError(Exception):
    """Roadmap #G - raised by create_daily_game when the caller already has a game for today's
    challenge of this (game_type, mode) - "1 intento por día" (decision [C]). main.py maps this to
    a 409."""
