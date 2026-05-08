from abc import ABC, abstractmethod

from src.domain.entities.settings import Settings


class SettingsRepository(ABC):

    @abstractmethod
    async def get(self) -> Settings | None:
        pass

    @abstractmethod
    async def save(self, settings: Settings) -> Settings:
        pass