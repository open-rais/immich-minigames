from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    game_slug: str = ""
    mode_slug: str = ""

    score: int = 0
    streak: int = 0
    rounds_played: int = 0

    is_active: bool = True
    is_game_over: bool = False

    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)

    game_state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.game_slug:
            raise ValueError("game_slug is required")
        if not self.mode_slug:
            raise ValueError("mode_slug is required")
        