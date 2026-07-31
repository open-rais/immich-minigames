"""Roadmap #G (daily games) - Immichdle's DailySupport implementation (games/daily.py's contract):
generates a day's shared content, decides which ids future days must avoid repeating, and builds
the kwargs to replay it against the *same* ImmichdleGame class a normal game uses (see
docs/TODO/DECOUPLING.md decision C). Immichdle has no round sequence to precompute - its only
content is the target, and guesses stay live either way (ImmichdleGame.play_round always queries
immich_service for whatever the player types) - so unlike the other games, this needs no separate
content seam in games/immichdle/game.py; ImmichdleGame.start()'s existing optional `target` param
already covers it."""

from typing import Any
from uuid import UUID

from games.immichdle.game import ASSET_COUNT_WEIGHT_EXPONENT
from games.immichdle.round import PersonSnapshot
from services.immich import ImmichService
from services.ml_service import MLService


def build_spec(mode: str, immich_service: ImmichService, settings: dict[str, float]) -> dict[str, Any]:
    # Replicates ImmichdleGame.start()'s target-selection directly rather than driving a full game
    # instance, since there's no round sequence to precompute.
    weight = float(settings.get("asset_count_weight", ASSET_COUNT_WEIGHT_EXPONENT))
    targets = immich_service.get_persons(named_only=True, randomize=True, limit=1, asset_count_weight=weight)
    if not targets:
        raise ValueError("not enough named people in Immich to generate a daily Immichdle challenge")
    [target_person] = targets
    # Mirrors ImmichdleGame.start()'s has_alternative check - with exactly one named person the
    # normal game refuses to start (the target would be trivially guessable), so the daily must
    # too. Phrased as "at least two named people exist" - equivalent to "someone besides the
    # (named) target exists". When a no-repeat-window wrapper widens this query's exclusions the
    # check can come out stricter than the real game's, but a failure then just triggers
    # get_or_create_challenge's no-exclusion retry, where it's exact.
    if len(immich_service.get_persons(named_only=True, limit=2)) < 2:
        raise ValueError("not enough named people in Immich to generate a daily Immichdle challenge")
    target = PersonSnapshot.of(
        target_person, first_asset_date=immich_service.get_person_first_asset_date(target_person.id)
    )
    return {"target": target.to_dict()}


def exclusion_ids(spec: dict[str, Any]) -> set[UUID]:
    return {UUID(spec["target"]["id"])}


def game_kwargs(
    mode: str,
    spec: dict[str, Any],
    settings: dict[str, float],
    *,
    rounds_played: int,
    immich_service: ImmichService,
    ml_service: MLService,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"immich_service": immich_service, "ml_service": ml_service, "settings": settings}
    # Only the very first round needs the target explicitly - ImmichdleRound.from_payload already
    # carries it for every later reconstruction (see games/immichdle/game.py's ImmichdleGame.target).
    if rounds_played == 0:
        kwargs["target"] = PersonSnapshot.from_dict(spec["target"])
    return kwargs
