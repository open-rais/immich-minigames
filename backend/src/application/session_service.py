from datetime import datetime

from src.application.game_registry import (
    get_game_registry,
)
from src.domain.entities.session import Session
from src.domain.repositories.session_repository import (
    SessionRepository,
)
from src.infraestructure.immich.provider import (
    ImmichProvider,
)


class SessionService:
    """Gameplay orchestration service."""

    def __init__(
        self,
        session_repository: SessionRepository,
        immich_provider: ImmichProvider,
    ) -> None:
        self.repository = session_repository
        self.immich = immich_provider

    async def create_session(
        self,
        game_slug: str,
        mode_slug: str,
    ) -> tuple[Session, dict]:
        registry = get_game_registry()

        if not registry.is_registered(game_slug):
            raise ValueError(
                f"Game '{game_slug}' is not registered"
            )

        plugin_factory = registry.get(game_slug)
        plugin = plugin_factory(self.immich)

        game_info = await plugin.get_game_info()

        valid_modes = [
            mode.slug
            for mode in game_info.modes
        ]

        if mode_slug not in valid_modes:
            raise ValueError(
                f"Mode '{mode_slug}' is not valid "
                f"for game '{game_slug}'"
            )

        session = Session(
            game_slug=game_slug,
            mode_slug=mode_slug,
        )

        initial_round = await plugin.start_session(
            session
        )

        session = await self.repository.create(
            session
        )

        return session, initial_round

    async def get_session(
        self,
        session_id: str,
    ) -> Session | None:
        session = await self.repository.get(
            session_id
        )

        if not session:
            return None

        if not session.is_active:
            return None

        return session

    async def submit_answer(
        self,
        session_id: str,
        answer: str,
    ) -> dict:
        session = await self.get_session(
            session_id
        )

        if not session:
            raise ValueError(
                "Session not found"
            )

        registry = get_game_registry()

        plugin_factory = registry.get(
            session.game_slug
        )

        plugin = plugin_factory(self.immich)

        result = await plugin.submit_answer(
            session=session,
            answer=answer,
        )

        session.last_activity_at = (
            datetime.utcnow()
        )

        await self.repository.update(session)

        return result

    async def end_session(
        self,
        session_id: str,
    ) -> bool:
        return await self.repository.delete(
            session_id
        )
