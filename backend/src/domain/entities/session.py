from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Session:
    """Represents an active game session.
    
    A session tracks the current state of a player playing a game.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    game_slug: str = ""
    mode_slug: str = ""
    score: int = 0
    rounds_played: int = 0
    current_round_id: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate session data."""
        if not self.game_slug:
            raise ValueError("game_slug is required")
        if not self.mode_slug:
            raise ValueError("mode_slug is required")
