from dataclasses import dataclass
from typing import Any


@dataclass
class GameMode:
    """Represents a game mode (e.g., 'person-items', 'album-items')."""
    slug: str
    name: str
    description: str


@dataclass
class Game:
    """Represents a game with its metadata and modes."""
    slug: str
    name: str
    description: str
    modes: list[GameMode]


@dataclass
class Round:
    """Represents a single game round."""
    game_slug: str
    mode_slug: str
    question: dict[str, Any]
    correct_answer: Any
    user_answer: Any | None = None
    score: int = 0
    is_correct: bool = False
