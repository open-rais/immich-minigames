"""Service-layer exceptions shared by more than one services/*.py module - kept in their own
module (rather than living in whichever service defined them first) specifically to avoid a
circular import: services/games_service.py's GamesService.create_daily_game delegates challenge
generation to services/daily_service.py's DailyService, which needs to raise the very same
NotEnoughContentError games_service.py already defined for its own games' start() failures."""


class UnsupportedGameError(Exception):
    pass


class NotEnoughContentError(Exception):
    """Raised when the Immich library doesn't have enough named people/faces/located assets to
    start a game - the friendly ValueError each game's start() already raises for that case (see
    games/more_or_less.py, games/immichdle.py, games/whos_that_person.py, games/asset_rounds.py),
    re-raised here so main.py can map it to a 422 instead of it reaching the client as a bare 500.
    Also raised by services/daily_service.py when a daily challenge can't be generated at all."""
