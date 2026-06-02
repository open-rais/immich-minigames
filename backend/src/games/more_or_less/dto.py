from dataclasses import asdict, dataclass
from typing import Literal


GuessType = Literal["more", "less"]


@dataclass
class PersonItem:
    id: str
    name: str
    thumbnail_url: str | None
    asset_count: int

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class PublicPerson:
    id: str
    name: str
    thumbnail_url: str | None
    asset_count: int | None = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class PublicRound:
    left_person: PublicPerson
    right_person: PublicPerson

    def model_dump(self) -> dict:
        return {
            "left_person": self.left_person.model_dump(),
            "right_person": self.right_person.model_dump(),
        }
