"""Pydantic request/response DTOs for the REST API - separate from the domain objects in
games/*.py. One module per game (more_or_less.py, geoguessr.py, dateguessr.py, immichdle.py,
whos_that_person.py) holds that game's *RoundOut/*PlayRoundIn pair; common.py holds everything
that spans every game (CreateGameIn, GameOut, PlayRoundOut, the RoundOut discriminated union, the
per-round-type registry picking the right guess schema/output DTO) plus the person-search DTOs,
which aren't game-specific at all."""
