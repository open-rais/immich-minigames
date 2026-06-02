from dataclasses import dataclass


@dataclass
class GameMode:
    slug: str
    name: str
    description: str


@dataclass
class Game:
    slug: str
    name: str
    description: str
    modes: list[GameMode]
    