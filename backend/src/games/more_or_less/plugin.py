from src.domain.entities.game import Game, GameMode
from src.domain.entities.game_plugin import GamePlugin
from src.domain.entities.session import Session

from src.games.more_or_less.selectors import (
    select_person_pair,
)
from src.games.more_or_less.engine import (
    build_public_round,
    determine_answer,
)
from src.games.more_or_less.scoring import (
    calculate_score,
)

from src.infraestructure.immich.provider import ImmichProvider


class MoreOrLessPlugin(GamePlugin):
    def __init__(
        self,
        immich_provider: ImmichProvider,
    ) -> None:
        self.immich = immich_provider

    async def get_game_info(self) -> Game:
        return Game(
            slug="more_or_less",
            name="More or Less",
            description="Guess if the next entity has more or less items",
            modes=[
                GameMode(
                    slug="person-items",
                    name="Person Items",
                    description="Compare person photo counts",
                ),
            ],
        )

    async def start_session(
        self,
        session: Session,
    ) -> dict:
        left_person, right_person = await select_person_pair(
            self.immich,
            used_ids=[],
        )

        correct_answer = determine_answer(
            left_person.asset_count,
            right_person.asset_count,
        )

        session.game_state = {
            "used_person_ids": [
                left_person.id,
                right_person.id,
            ],
            "current_round": {
                "left_person": left_person.model_dump(),
                "right_person": right_person.model_dump(),
                "correct_answer": correct_answer,
            },
        }

        return build_public_round(
            left_person=left_person,
            right_person=right_person,
        )

    async def submit_answer(
        self,
        session: Session,
        answer: str,
    ) -> dict:
        current_round = session.game_state["current_round"]

        correct_answer = current_round["correct_answer"]

        is_correct = answer == correct_answer

        right_person = current_round["right_person"]

        if not is_correct:
            session.is_game_over = True
            session.is_active = False

            return {
                "correct": False,
                "game_over": True,
                "correct_answer": correct_answer,
                "revealed": {
                    "name": right_person["name"],
                    "asset_count": right_person["asset_count"],
                },
                "score": session.score,
                "streak": session.streak,
                "next_round": None,
            }

        session.rounds_played += 1
        session.streak += 1

        gained_score = calculate_score(
            streak=session.streak,
        )

        session.score += gained_score

        used_ids = session.game_state["used_person_ids"]

        next_left_person = current_round["right_person"]

        left_person_obj, right_person_obj = await select_person_pair(
            self.immich,
            used_ids=used_ids,
            forced_left_person_id=next_left_person["id"],
        )

        next_correct_answer = determine_answer(
            left_person_obj.asset_count,
            right_person_obj.asset_count,
        )

        session.game_state["used_person_ids"].append(
            right_person_obj.id
        )

        session.game_state["current_round"] = {
            "left_person": left_person_obj.model_dump(),
            "right_person": right_person_obj.model_dump(),
            "correct_answer": next_correct_answer,
        }

        return {
            "correct": True,
            "game_over": False,
            "revealed": {
                "name": right_person["name"],
                "asset_count": right_person["asset_count"],
            },
            "score": session.score,
            "streak": session.streak,
            "next_round": build_public_round(
                left_person=left_person_obj,
                right_person=right_person_obj,
            ).model_dump(),
        }
