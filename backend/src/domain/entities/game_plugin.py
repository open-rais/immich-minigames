from abc import ABC, abstractmethod

from src.domain.entities.game import Game
from src.domain.entities.session import Session


class GamePlugin(ABC):
    """Contract: session-driven gameplay."""

    @abstractmethod
    async def get_game_info(self) -> Game:
        pass

    @abstractmethod
    async def start_session(self, session: Session) -> dict:
        """Initialize session and return first round payload."""
        pass

    @abstractmethod
    async def submit_answer(self, session: Session, answer: str) -> dict:
        """Process answer and return updated state + next round."""
        pass
    