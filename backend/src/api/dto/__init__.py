"""Pydantic request/response DTOs for the REST API - separate from the domain objects in
games/*.py. One module per game (more_or_less.py, geoguessr.py, dateguessr.py, immichdle.py,
whos_that_person.py, timeline.py) holds that game's *RoundOut/*PlayRoundIn pair; common.py holds what spans
every game/mode (CreateGameIn, GameOut, PlayRoundOut, the RoundOut discriminated union, the
per-round-type registry picking the right guess schema/output DTO). Everything else that isn't
game-specific but also doesn't belong in common.py gets its own module: persons.py (person search),
records.py (personal bests), leaderboard.py (normal + daily leaderboards), daily.py (daily-game
player-facing status), admin.py (admin-editable game/daily settings), config.py (public runtime
config)."""
