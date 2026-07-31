"""
Based on Who's That Pokémon. A photo is shown with some of its already-named detected faces blacked
out (up to MAX_HIDDEN_FACES) - the player identifies every blacked-out face before submitting. A
round is one photo: even when it hides several faces, they're all answered in a single submit, so
the round keeps the same one-guess shape every other game uses (see BaseRound.guess). The same
person can appear twice in one photo (mirrors, collages, etc.) - each hidden face is graded
independently against its own true person, never deduplicated. Faces without a name are never
blacked out (there'd be nothing to grade), so a photo can have more visible faces than hidden ones.
See docs/GAMES/WHOS_THAT_PERSON.md.

The game asks about TOTAL_PEOPLE people total, across as many rounds as it takes to reach that
count - a round's face count is capped so the running total never overshoots it.

Scoring is a combo streak counted by person, not by round - see games/whos_that_person/round.py's
WhosThatPersonRound.calculate_score for the exact streak rules. *Which* photo/faces a round gets is
a separate axis of variation (games/whos_that_person/content.py's WhosThatPersonContent) - live
Immich queries normally, a frozen daily spec for the daily flow
(games/whos_that_person/daily.py's ScriptedContent).
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

from games.base import BaseGame, PlayRoundResult
from games.whos_that_person.content import WhosThatPersonContent
from games.whos_that_person.round import WhosThatPersonRound
from services.immich import ContentQueries

GAME_TYPE = "whos-that-person"
MODE_NAMED_FACES = "namedFaces"

# Admin feature - public (no leading underscore) since games/settings_registry.py assembles these
# as defaults for the admin-configurable total_people/max_hidden_faces settings, same convention
# already used by e.g. games/geoguessr/game.py's TOTAL_ROUNDS/MAX_SCORE.
TOTAL_PEOPLE = 15
MAX_HIDDEN_FACES = 5


class IncompleteGuessError(Exception):
    pass


class WhosThatPersonGame(BaseGame):
    def __init__(
        self,
        id: UUID,
        rounds: list[WhosThatPersonRound],
        immich_service: ContentQueries,
        content: WhosThatPersonContent,
        score: int = 0,
        finished: bool = False,
        settings: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            game_type=GAME_TYPE,
            mode=MODE_NAMED_FACES,
            rounds=rounds,
            score=score,
            finished=finished,
            settings=settings,
        )
        # Always live, daily or not - unlike content (which round's photo/faces come from), guess
        # resolution (play_round below) always needs a fresh name lookup for whatever the player
        # actually typed, regardless of where the round's content itself came from.
        self._immich_service = immich_service
        self._content = content

    @property
    def _people_asked(self) -> int:
        return sum(len(round_.faces) for round_ in self.rounds)

    # -- admin-configurable (see games/settings_registry.py) ----------

    @property
    def total_people(self) -> int:
        # Public (no leading underscore) - api/dto/common.py's GameOut reads this to show the
        # frontend the *live* total instead of the hardcoded display-only constant it used to
        # mirror.
        return int(self._settings.get("total_people", TOTAL_PEOPLE))

    @property
    def _max_hidden_faces(self) -> int:
        return int(self._settings.get("max_hidden_faces", MAX_HIDDEN_FACES))

    @property
    def _shown_asset_ids(self) -> frozenset[UUID]:
        # Never repeat the same photo within a game (unlike people, who can and will repeat across
        # photos - the named-people pool is much smaller than 15).
        return frozenset(round_.asset_id for round_ in self.rounds)

    @classmethod
    def start(
        cls,
        id: UUID,
        immich_service: ContentQueries,
        content: WhosThatPersonContent,
        settings: Mapping[str, float] | None = None,
    ) -> "WhosThatPersonGame":
        game = cls(id=id, rounds=[], immich_service=immich_service, content=content, settings=settings)
        picked = game._content.pick_round(min(game._max_hidden_faces, game.total_people), frozenset())
        if picked is None:
            raise ValueError("not enough named faces in Immich to start a Who'sThatPerson game")

        asset_id, faces = picked
        first_round = WhosThatPersonRound(id=uuid4(), game_id=id, round_index=1, asset_id=asset_id, faces=faces)
        game.rounds.append(first_round)
        return game

    def play_round(self, guess: dict[UUID, UUID]) -> PlayRoundResult:
        if self.finished:
            raise ValueError("game is already finished")
        expected_face_ids = {face.face_id for face in self.current_round.faces}
        if set(guess) != expected_face_ids:
            raise IncompleteGuessError("guess must include exactly one entry per hidden face in the round")
        # Frozen here rather than looked up again whenever the round is later displayed - one query
        # for every guessed person in this round, not one per face. A guessed id that no longer
        # resolves to a real person (deleted from Immich since) just doesn't show up in the result,
        # leaving that face's name unresolved.
        guessed_person_ids = frozenset(guess.values())
        persons = self._immich_service.get_persons(
            named_only=True, ids=guessed_person_ids, limit=len(guessed_person_ids)
        )
        self.current_round.guess_names = {person.id: person.name for person in persons}
        return super().play_round(guess)

    def has_next_round(self) -> bool:
        if self._people_asked >= self.total_people:
            return False
        max_faces = min(self._max_hidden_faces, self.total_people - self._people_asked)
        return self._content.has_more(max_faces, self._shown_asset_ids)

    def create_next_round(self) -> WhosThatPersonRound:
        previous = self.current_round
        max_faces = min(self._max_hidden_faces, self.total_people - self._people_asked)
        picked = self._content.pick_round(max_faces, self._shown_asset_ids)
        if picked is None:
            raise ValueError("no more eligible photos left - has_next_round() should have returned False")
        asset_id, faces = picked

        return WhosThatPersonRound(
            id=uuid4(),
            game_id=self.id,
            round_index=previous.round_index + 1,
            asset_id=asset_id,
            faces=faces,
            incoming_streak=previous.ending_streak,
        )
