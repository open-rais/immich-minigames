from src.games.more_or_less.dto import GuessType, PublicRound, PublicRound, PublicPerson


class MoreOrLessEngine:
    def create_round(self, left, right) -> PublicRound:
        correct: GuessType = "more" if right.asset_count > left.asset_count else "less"

        return PublicRound(
            left_person=left,
            right_person=right,
            correct_answer=correct,
        )

    def validate(self, round_data: PublicRound, answer: GuessType) -> bool:
        return round_data.correct_answer == answer

    def to_public(self, round_data: PublicRound) -> PublicRound:
        return PublicRound(
            left_person=PublicPerson(
                id=round_data.left_person.id,
                name=round_data.left_person.name,
                thumbnail_url=round_data.left_person.thumbnail_url,
                asset_count=round_data.left_person.asset_count,
            ),
            right_person=PublicPerson(
                id=round_data.right_person.id,
                name=round_data.right_person.name,
                thumbnail_url=round_data.right_person.thumbnail_url,
                asset_count=None,
            ),
        )

def build_public_round(left_person, right_person):
    return PublicRound(
        left_person=PublicPerson(
            id=left_person.id,
            name=left_person.name,
            thumbnail_url=left_person.thumbnail_url,
            asset_count=left_person.asset_count,
        ),
        right_person=PublicPerson(
            id=right_person.id,
            name=right_person.name,
            thumbnail_url=right_person.thumbnail_url,
            asset_count=right_person.asset_count,
        ),
    )

def determine_answer(left_count: int, right_count: int) -> str:
    if left_count == right_count:
        return "equal"
    return "more" if right_count > left_count else "less"

__all__ = [
    "build_public_round",
    "determine_answer",
    "MoreOrLessEngine",
]
