from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.settings import Settings
from src.domain.repositories.settings_repository import SettingsRepository
from src.infraestructure.db.models.settings import SettingsModel


class SQLAlchemySettingsRepository(SettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> Settings | None:
        """Retrieve settings from database."""
        query = select(SettingsModel).where(
            SettingsModel.key.in_(["immich_url", "immich_api_key"])
        )
        result = await self.session.execute(query)
        rows = result.scalars().all()

        if not rows:
            return None

        settings_dict = {row.key: row.value for row in rows}

        immich_url = settings_dict.get("immich_url")
        immich_api_key = settings_dict.get("immich_api_key")

        if not immich_url or not immich_api_key:
            return None

        return Settings(
            immich_url=immich_url,
            immich_api_key=immich_api_key,
        )

    async def save(self, settings: Settings) -> Settings:
        """Save or update settings in database."""
        settings_data = [
            ("immich_url", settings.immich_url),
            ("immich_api_key", settings.immich_api_key),
        ]

        for key, value in settings_data:
            existing = await self.session.execute(
                select(SettingsModel).where(SettingsModel.key == key)
            )
            row = existing.scalar_one_or_none()

            if row:
                row.value = value
            else:
                row = SettingsModel(key=key, value=value)
                self.session.add(row)

        await self.session.flush()
        await self.session.commit()
        return settings