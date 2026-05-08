"""MoreOrLess game implementation.

Inspired by "Higher or Lower" - Player guesses if next entity has more/less of something.

Modes:
- person-items: Compare item counts between persons
- album-items: Compare item counts between albums  
- timeline: Compare dates between assets
"""

from typing import Any

from src.domain.entities.game import Game, GameMode, Round
from src.domain.entities.game_plugin import GamePlugin
from src.infraestructure.immich.provider import ImmichProvider


class MoreOrLessGame(GamePlugin):
    """MoreOrLess game plugin implementation."""

    def __init__(self, immich_provider: ImmichProvider) -> None:
        """Initialize MoreOrLess game.
        
        Args:
            immich_provider: ImmichProvider instance for data access
        """
        self.immich = immich_provider

    async def get_game_info(self) -> Game:
        """Return game metadata."""
        return Game(
            slug="more_or_less",
            name="More or Less",
            description="Guess if the next entity has more or less of something",
            modes=[
                GameMode(
                    slug="person-items",
                    name="Person Items",
                    description="Compare item counts between persons",
                ),
                GameMode(
                    slug="album-items",
                    name="Album Items",
                    description="Compare item counts between albums",
                ),
                GameMode(
                    slug="timeline",
                    name="Timeline",
                    description="Compare dates between assets",
                ),
            ],
        )

    async def generate_round(self, mode_slug: str) -> Round:
        """Generate a new round for the given mode."""
        if mode_slug == "person-items":
            return await self._generate_person_items_round()
        elif mode_slug == "album-items":
            return await self._generate_album_items_round()
        elif mode_slug == "timeline":
            return await self._generate_timeline_round()
        else:
            raise ValueError(f"Invalid mode: {mode_slug}")

    async def validate_answer(
        self,
        mode_slug: str,
        correct_answer: Any,
        user_answer: Any,
    ) -> bool:
        """Validate the user's answer."""
        if mode_slug == "person-items":
            # correct_answer: "more" | "less"
            # user_answer: "more" | "less"
            return correct_answer == user_answer
        elif mode_slug == "album-items":
            return correct_answer == user_answer
        elif mode_slug == "timeline":
            # correct_answer: "newer" | "older"
            # user_answer: "newer" | "older"
            return correct_answer == user_answer
        else:
            raise ValueError(f"Invalid mode: {mode_slug}")

    async def calculate_score(
        self,
        mode_slug: str,
        correct_answer: Any,
        user_answer: Any,
        is_correct: bool,
    ) -> int:
        """Calculate score for the round."""
        if is_correct:
            return 100  # Base score for correct answer
        return 0

    # =======================================================================
    # Mode-specific implementations
    # =======================================================================

    async def _generate_person_items_round(self) -> Round:
        """Generate a round comparing person item counts."""
        person_a = await self.immich.get_random_person()
        person_b = await self.immich.get_random_person()

        # Avoid comparing same person
        while person_b.id == person_a.id:
            person_b = await self.immich.get_random_person()

        # Determine correct answer
        correct_answer = (
            "more" if person_b.asset_count > person_a.asset_count else "less"
        )

        question = {
            "person_a": {
                "id": person_a.id,
                "name": person_a.name,
                "asset_count": person_a.asset_count,
            },
            "person_b_name": person_b.name,
            "text": f"{person_a.name} has {person_a.asset_count} photos. "
            f"Does {person_b.name} have MORE or LESS photos?",
        }

        return Round(
            game_slug="more_or_less",
            mode_slug="person-items",
            question=question,
            correct_answer=correct_answer,
        )

    async def _generate_album_items_round(self) -> Round:
        """Generate a round comparing album item counts."""
        album_a = await self.immich.get_random_album()
        album_b = await self.immich.get_random_album()

        # Avoid comparing same album
        while album_b.id == album_a.id:
            album_b = await self.immich.get_random_album()

        # Determine correct answer
        correct_answer = (
            "more" if album_b.asset_count > album_a.asset_count else "less"
        )

        question = {
            "album_a": {
                "id": album_a.id,
                "name": album_a.album_name,
                "asset_count": album_a.asset_count,
            },
            "album_b_name": album_b.album_name,
            "text": f"{album_a.album_name} has {album_a.asset_count} photos. "
            f"Does {album_b.album_name} have MORE or LESS photos?",
        }

        return Round(
            game_slug="more_or_less",
            mode_slug="album-items",
            question=question,
            correct_answer=correct_answer,
        )

    async def _generate_timeline_round(self) -> Round:
        """Generate a round comparing asset dates."""
        asset_a = await self.immich.get_random_asset()
        asset_b = await self.immich.get_random_asset()

        # Avoid comparing same asset
        while asset_b.id == asset_a.id:
            asset_b = await self.immich.get_random_asset()

        # Determine correct answer based on file_created_at
        from datetime import datetime
        
        date_a = asset_a.file_created_at
        date_b = asset_b.file_created_at
        
        if isinstance(date_a, str):
            date_a = datetime.fromisoformat(date_a.replace("Z", "+00:00"))
        if isinstance(date_b, str):
            date_b = datetime.fromisoformat(date_b.replace("Z", "+00:00"))

        correct_answer = "newer" if date_b > date_a else "older"

        question = {
            "asset_a": {
                "id": asset_a.id,
                "date": date_a.isoformat() if hasattr(date_a, 'isoformat') else str(date_a),
            },
            "asset_b": {
                "id": asset_b.id,
            },
            "text": f"This photo was taken on {date_a.date()}. "
            f"Is the next photo NEWER or OLDER?",
        }

        return Round(
            game_slug="more_or_less",
            mode_slug="timeline",
            question=question,
            correct_answer=correct_answer,
        )
