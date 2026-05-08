from dataclasses import dataclass


@dataclass
class GameStats:
    """Represents statistics for a game mode.
    
    Tracks high scores and play count for a specific game/mode combination.
    """
    game_slug: str
    mode_slug: str
    best_score: int = 0
    times_played: int = 0
