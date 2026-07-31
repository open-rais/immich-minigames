"""Persistence layer for this app's own games/rounds tables (persistence/games.py) - the only
module directly issuing SQLAlchemy queries/mutations against GameModel/RoundModel. Every service
that needs to read or write a game row (services/games_service.py, services/daily_games_service.py,
services/scores_service.py) depends on this instead of touching the session itself, so none of them
has to duplicate a SELECT/UPDATE shape the others already need.
"""

from collections.abc import Sequence
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import Row, func, or_, select, tuple_
from sqlalchemy.orm import Session

from games.base import BaseGame, BaseRound
from persistence.daily import DailyChallengeModel
from persistence.games import GameModel, RoundModel
from persistence.users import UserModel


class GameRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        # Populated by get_for_update() and consulted by save_played_round() so playing a round
        # never has to re-fetch (and assume the existence of) a GameModel row this same repository
        # instance already loaded earlier in the request.
        self._loaded_rows: dict[UUID, GameModel] = {}

    def get_for_update(self, game_id: UUID) -> GameModel | None:
        # SELECT ... FOR UPDATE - this is the single load point for both viewing a game and
        # loading it right before playing a round, so locking it here closes the race where two
        # simultaneous plays of the same round both pass play_loaded_round's current_round.id check
        # and both score. Everything happens in one transaction per request (api/deps.py's
        # get_db_session), so the lock is held for at most one request.
        game_row = self._session.get(GameModel, game_id, with_for_update=True)
        if game_row is not None:
            self._loaded_rows[game_row.id] = game_row
        return game_row

    def get_active(self, game_type: str, mode: str, user_id: UUID) -> GameModel | None:
        # ORDER BY created_at DESC LIMIT 1 rather than scalar_one() deliberately tolerates more
        # than one matching row (a stray unfinished game left over from before the `abandoned`
        # column existed, or the documented cross-tab race in abandon_active) by just picking the
        # most recent, instead of crashing.
        return self._session.execute(
            select(GameModel)
            .where(
                GameModel.game_type == game_type,
                GameModel.mode == mode,
                GameModel.finished.is_(False),
                GameModel.abandoned.is_(False),
                # A daily game lives in its own world, resumed only through its own status
                # endpoint - the normal idle screen's "Continuar" must never surface one.
                GameModel.daily_challenge_id.is_(None),
                GameModel.user_id == user_id,
            )
            .order_by(GameModel.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_recent(self, user_id: UUID, limit: int) -> Sequence[GameModel]:
        return (
            self._session.execute(
                select(GameModel)
                .where(
                    GameModel.user_id == user_id,
                    or_(GameModel.finished.is_(True), GameModel.abandoned.is_(True)),
                )
                .order_by(GameModel.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def personal_records(self, user_id: UUID) -> Sequence[Row]:
        return self._session.execute(
            select(GameModel.game_type, GameModel.mode, func.max(GameModel.score))
            .where(
                GameModel.finished.is_(True),
                # Daily scores aren't comparable to normal play (different settings, separate
                # leaderboard).
                GameModel.daily_challenge_id.is_(None),
                GameModel.user_id == user_id,
            )
            .group_by(GameModel.game_type, GameModel.mode)
        ).all()

    def leaderboard_rows(self, game_type: str, mode: str, window: Literal["all", "weekly", "daily"]) -> Sequence[Row]:
        best_score = func.max(GameModel.score).label("best_score")
        stmt = (
            select(UserModel.username, UserModel.skin_person_id, best_score)
            .select_from(GameModel)
            .join(UserModel, UserModel.id == GameModel.user_id)
            .where(
                GameModel.game_type == game_type,
                GameModel.mode == mode,
                GameModel.finished.is_(True),
                # The normal leaderboard never mixes in daily scores - the daily leaderboard is its
                # own query scoped to one challenge (see daily_leaderboard_rows below).
                GameModel.daily_challenge_id.is_(None),
            )
            .group_by(UserModel.id, UserModel.username, UserModel.skin_person_id)
            .order_by(best_score.desc())
            .limit(15)
        )
        if window != "all":
            # Postgres's date_trunc('week', ...) is Monday-based (ISO 8601), matching "semanal
            # desde el lunes" as confirmed with the project owner.
            trunc_unit = "day" if window == "daily" else "week"
            stmt = stmt.where(GameModel.created_at >= func.date_trunc(trunc_unit, func.now()))
        return self._session.execute(stmt).all()

    def daily_challenge_id(self, game_type: str, mode: str, challenge_date: date) -> UUID | None:
        return self._session.execute(
            select(DailyChallengeModel.id).where(
                DailyChallengeModel.challenge_date == challenge_date,
                DailyChallengeModel.game_type == game_type,
                DailyChallengeModel.mode == mode,
            )
        ).scalar_one_or_none()

    def daily_leaderboard_rows(self, challenge_id: UUID) -> Sequence[Row]:
        best_score = func.max(GameModel.score).label("best_score")
        stmt = (
            select(UserModel.username, UserModel.skin_person_id, best_score)
            .select_from(GameModel)
            .join(UserModel, UserModel.id == GameModel.user_id)
            .where(GameModel.daily_challenge_id == challenge_id, GameModel.finished.is_(True))
            .group_by(UserModel.id, UserModel.username, UserModel.skin_person_id)
            .order_by(best_score.desc())
            .limit(15)
        )
        return self._session.execute(stmt).all()

    def has_played_challenge(self, challenge_id: UUID, user_id: UUID) -> bool:
        return (
            self._session.execute(
                select(GameModel.id).where(GameModel.daily_challenge_id == challenge_id, GameModel.user_id == user_id)
            ).scalar_one_or_none()
            is not None
        )

    def challenges_for_date(
        self, today: date, modes: Sequence[tuple[str, str]]
    ) -> dict[tuple[str, str], DailyChallengeModel]:
        return {
            (challenge.game_type, challenge.mode): challenge
            for challenge in self._session.execute(
                select(DailyChallengeModel).where(
                    DailyChallengeModel.challenge_date == today,
                    tuple_(DailyChallengeModel.game_type, DailyChallengeModel.mode).in_(modes),
                )
            ).scalars()
        }

    def games_for_challenges(self, challenge_ids: Sequence[UUID], user_id: UUID) -> dict[UUID, GameModel]:
        if not challenge_ids:
            return {}
        return {
            row.daily_challenge_id: row
            for row in self._session.execute(
                select(GameModel).where(GameModel.daily_challenge_id.in_(challenge_ids), GameModel.user_id == user_id)
            ).scalars()
        }

    def abandon_active(self, game_type: str, mode: str, user_id: UUID) -> None:
        # Marks *every* matching row rather than assuming there's ever only one - self-heals any
        # stray unfinished game left over from before the `abandoned` column existed, or from the
        # documented cross-tab race (two tabs both starting a new game for the same mode).
        rows = (
            self._session.execute(
                select(GameModel).where(
                    GameModel.game_type == game_type,
                    GameModel.mode == mode,
                    GameModel.finished.is_(False),
                    GameModel.abandoned.is_(False),
                    # Starting a normal game must never abandon an in-progress daily of the same
                    # mode (and vice versa) - a daily challenge only ever gets one game per player
                    # in the first place.
                    GameModel.daily_challenge_id.is_(None),
                    GameModel.user_id == user_id,
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.abandoned = True

    def save_new(self, game: BaseGame, user_id: UUID, daily_challenge_id: UUID | None = None) -> None:
        game_row = GameModel(
            id=game.id,
            user_id=user_id,
            game_type=game.game_type,
            mode=game.mode,
            score=game.score,
            finished=game.finished,
            daily_challenge_id=daily_challenge_id,
        )
        game_row.rounds.append(self._round_to_row(game.rounds[0]))
        self._session.add(game_row)
        self._session.commit()

    def save_played_round(self, game: BaseGame, answered_round: BaseRound) -> None:
        # No session.get() re-fetch here - the row was already loaded (and, on the play path,
        # FOR UPDATE-locked) by get_for_update earlier in this same repository instance/request, so
        # re-querying it by id would be redundant and, being Optional, would need an unjustified
        # existence check for a row we know is already in the session.
        game_row = self._loaded_rows.get(game.id)
        if game_row is None:
            raise RuntimeError(
                f"save_played_round called for game {game.id}, which was never loaded via get_for_update"
            )
        game_row.score = game.score
        game_row.finished = game.finished

        round_row = next((r for r in game_row.rounds if r.id == answered_round.id), None)
        if round_row is None:
            raise RuntimeError(f"round {answered_round.id} not found among already-loaded rows of game {game.id}")
        round_row.score_delta = answered_round.score_delta
        round_row.payload = answered_round.to_payload()

        if game.rounds[-1].id != answered_round.id:
            game_row.rounds.append(self._round_to_row(game.rounds[-1]))

        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()

    @staticmethod
    def _round_to_row(round_: BaseRound) -> RoundModel:
        return RoundModel(
            id=round_.id,
            round_index=round_.round_index,
            score_delta=round_.score_delta,
            payload=round_.to_payload(),
        )
