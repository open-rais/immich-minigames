"""Single source of truth for which (game_type, mode) maps to which game/round classes and, for
the daily-enabled ones, which `games/<game>/daily.py` module implements the `DailySupport`
contract (games/daily.py). Lives in `games/` (pure knowledge of which game/mode maps to what, no
persistence/business logic) rather than `services/games_service.py`, since
`services/daily_challenge_service.py` needs to read it too without creating the same import cycle
services/errors.py's docstring already documents for NotEnoughContentError:
services/daily_games_service.py depends on daily_challenge_service.py (to delegate challenge
generation), so daily_challenge_service.py must never depend back on either of them.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import games.dateguessr.daily as dateguessr_daily
import games.geoguessr.daily as geoguessr_daily
import games.immichdle.daily as immichdle_daily
import games.more_or_less.daily as more_or_less_daily
import games.timeline.daily as timeline_daily
import games.whos_that_person.daily as whos_that_person_daily
from games.base import BaseGame, BaseRound
from games.daily import DailySupport
from games.dateguessr import GAME_TYPE as DATEGUESSR_TYPE
from games.dateguessr import MODE_DAYS_TO_DATE, DateguessrGame, DateguessrRound
from games.dateguessr import LiveContent as DateguessrLiveContent
from games.geoguessr import GAME_TYPE as GEOGUESSR_TYPE
from games.geoguessr import MODE_DISTANCE_BETWEEN_GUESS, GeoguessrGame, GeoguessrRound
from games.geoguessr import LiveContent as GeoguessrLiveContent
from games.immichdle import GAME_TYPE as IMMICHDLE_TYPE
from games.immichdle import MODE_ALBUM, MODE_PERSON, AlbumdleGame, AlbumdleRound, PersondleGame, PersondleRound
from games.more_or_less import GAME_TYPE as MORE_OR_LESS_TYPE
from games.more_or_less import (
    MODE_ALBUM_ASSETS,
    MODE_PERSON_ASSETS,
    MODE_PERSON_BIRTH_DATE,
    AlbumAssetsProvider,
    CandidateProvider,
    MoreOrLessGame,
    MoreOrLessRound,
    PersonAssetsProvider,
    PersonBirthDateProvider,
)
from games.timeline import GAME_TYPE as TIMELINE_TYPE
from games.timeline import MODE_ARCADE, TimelineGame, TimelineRound
from games.timeline import LiveContent as TimelineLiveContent
from games.whos_that_person import GAME_TYPE as WHOS_THAT_PERSON_TYPE
from games.whos_that_person import MODE_NAMED_FACES, WhosThatPersonGame, WhosThatPersonRound
from games.whos_that_person import LiveContent as WhosThatPersonLiveContent
from services.immich import ImmichService


@dataclass(frozen=True)
class GameSpec:
    """One registry entry per (game_type, mode) - single source of truth for which game/round
    classes a combination maps to, so adding a game only ever means adding one entry here.

    `provider_factory` is only set for a multi-mode game whose modes differ solely in their data
    source (MoreOrLess: personAssets vs albumAssets) - when present, the game gets `provider` +
    `mode` *instead of* `immich_service`/`content`, since the provider fully replaces its data
    source. `content_factory` is set for a game whose content sourcing has been split out into a
    `<game>Content` protocol (Geoguessr/Dateguessr/WhosThatPerson) - when present, the game gets
    `content` built from it; WhosThatPerson additionally still needs `immich_service` directly (for
    live guess-name resolution, unrelated to content), handled as a per-class special case in
    services/game_factory.py, same pattern already used there for BaseImmichdleGame's ml_service.

    `daily` is the game's `games/<game>/daily.py` module (implementing `DailySupport`) for the
    (game_type, mode) combinations the daily rotation supports - None for a game/mode that doesn't
    (or doesn't yet, e.g. Timeline once implemented)."""

    game_class: type[BaseGame]
    round_class: type[BaseRound]
    provider_factory: Callable[[ImmichService], CandidateProvider] | None = None
    content_factory: Callable[[ImmichService], Any] | None = None
    daily: DailySupport | None = None


GAMES: dict[tuple[str, str], GameSpec] = {
    (MORE_OR_LESS_TYPE, MODE_PERSON_ASSETS): GameSpec(
        MoreOrLessGame, MoreOrLessRound, provider_factory=PersonAssetsProvider, daily=more_or_less_daily
    ),
    (MORE_OR_LESS_TYPE, MODE_ALBUM_ASSETS): GameSpec(
        MoreOrLessGame, MoreOrLessRound, provider_factory=AlbumAssetsProvider, daily=more_or_less_daily
    ),
    (MORE_OR_LESS_TYPE, MODE_PERSON_BIRTH_DATE): GameSpec(
        MoreOrLessGame, MoreOrLessRound, provider_factory=PersonBirthDateProvider, daily=more_or_less_daily
    ),
    (GEOGUESSR_TYPE, MODE_DISTANCE_BETWEEN_GUESS): GameSpec(
        GeoguessrGame, GeoguessrRound, content_factory=GeoguessrLiveContent, daily=geoguessr_daily
    ),
    (DATEGUESSR_TYPE, MODE_DAYS_TO_DATE): GameSpec(
        DateguessrGame, DateguessrRound, content_factory=DateguessrLiveContent, daily=dateguessr_daily
    ),
    (IMMICHDLE_TYPE, MODE_PERSON): GameSpec(PersondleGame, PersondleRound, daily=immichdle_daily),
    (IMMICHDLE_TYPE, MODE_ALBUM): GameSpec(AlbumdleGame, AlbumdleRound, daily=immichdle_daily),
    (WHOS_THAT_PERSON_TYPE, MODE_NAMED_FACES): GameSpec(
        WhosThatPersonGame,
        WhosThatPersonRound,
        content_factory=WhosThatPersonLiveContent,
        daily=whos_that_person_daily,
    ),
    (TIMELINE_TYPE, MODE_ARCADE): GameSpec(
        TimelineGame, TimelineRound, content_factory=TimelineLiveContent, daily=timeline_daily
    ),
}
