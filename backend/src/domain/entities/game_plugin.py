from abc import ABC, abstractmethod
from typing import Any

from src.domain.entities.game import Game, Round


class GamePlugin(ABC):
    """Abstract base class for all game plugins.
    
    Defines the contract that each game must implement.
    Uses Template Method pattern for game lifecycle.
    """

    @abstractmethod
    async def get_game_info(self) -> Game:
        """Return game metadata (slug, name, description, modes)."""
        pass

    @abstractmethod
    async def generate_round(self, mode_slug: str) -> Round:
        """Generate a new round for the given mode.
        
        Args:
            mode_slug: The game mode to generate round for
            
        Returns:
            Round object with question and correct_answer populated
            
        Raises:
            ValueError: If mode_slug is invalid for this game
        """
        pass

    @abstractmethod
    async def validate_answer(
        self,
        mode_slug: str,
        correct_answer: Any,
        user_answer: Any,
    ) -> bool:
        """Validate the user's answer.
        
        Args:
            mode_slug: The game mode
            correct_answer: The correct answer from generate_round
            user_answer: The user's submitted answer
            
        Returns:
            True if answer is correct, False otherwise
        """
        pass

    @abstractmethod
    async def calculate_score(
        self,
        mode_slug: str,
        correct_answer: Any,
        user_answer: Any,
        is_correct: bool,
    ) -> int:
        """Calculate score for the round.
        
        Args:
            mode_slug: The game mode
            correct_answer: The correct answer
            user_answer: The user's answer
            is_correct: Whether the answer was correct
            
        Returns:
            Score points for this round
        """
        pass
