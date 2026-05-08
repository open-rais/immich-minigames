from abc import ABC, abstractmethod
import random

from src.infraestructure.immich.schemas import PersonDTO, AlbumDTO, AssetDTO


class ImmichProvider(ABC):
    """Abstract interface for Immich data access.
    
    Adapter pattern: decouples Immich API from game logic.
    """

    @abstractmethod
    async def get_random_person(self) -> PersonDTO:
        """Get a random person."""
        pass

    @abstractmethod
    async def get_random_album(self) -> AlbumDTO:
        """Get a random album."""
        pass

    @abstractmethod
    async def get_random_asset(self) -> AssetDTO:
        """Get a random asset."""
        pass

    @abstractmethod
    async def get_person_by_id(self, person_id: str) -> PersonDTO:
        """Get a specific person."""
        pass

    @abstractmethod
    async def get_album_by_id(self, album_id: str) -> AlbumDTO:
        """Get a specific album."""
        pass

    @abstractmethod
    async def get_asset_by_id(self, asset_id: str) -> AssetDTO:
        """Get a specific asset."""
        pass


class ImmichProviderImpl(ImmichProvider):
    """Concrete implementation of ImmichProvider using HTTP client."""

    def __init__(self, http_client) -> None:
        """Initialize provider with HTTP client.
        
        Args:
            http_client: ImmichHTTPClient instance
        """
        from src.infraestructure.immich.client import ImmichHTTPClient
        
        if not isinstance(http_client, ImmichHTTPClient):
            raise TypeError("http_client must be ImmichHTTPClient instance")
        
        self.client = http_client
        self._people_cache: list[PersonDTO] | None = None
        self._albums_cache: list[AlbumDTO] | None = None
        self._assets_cache: list[AssetDTO] | None = None

    async def _load_people(self) -> list[PersonDTO]:
        """Load and cache people list."""
        if self._people_cache is None:
            self._people_cache = await self.client.list_people()
        return self._people_cache

    async def _load_albums(self) -> list[AlbumDTO]:
        """Load and cache albums list."""
        if self._albums_cache is None:
            self._albums_cache = await self.client.list_albums()
        return self._albums_cache

    async def _load_assets(self) -> list[AssetDTO]:
        """Load and cache assets list."""
        if self._assets_cache is None:
            self._assets_cache = await self.client.list_assets()
        return self._assets_cache

    async def get_random_person(self) -> PersonDTO:
        """Get a random person."""
        people = await self._load_people()
        
        if not people:
            raise ValueError("No people found in Immich library")
        
        return random.choice(people)

    async def get_random_album(self) -> AlbumDTO:
        """Get a random album."""
        albums = await self._load_albums()
        
        if not albums:
            raise ValueError("No albums found in Immich library")
        
        return random.choice(albums)

    async def get_random_asset(self) -> AssetDTO:
        """Get a random asset."""
        assets = await self._load_assets()
        
        if not assets:
            raise ValueError("No assets found in Immich library")
        
        return random.choice(assets)

    async def get_person_by_id(self, person_id: str) -> PersonDTO:
        """Get a specific person."""
        return await self.client.get_person(person_id)

    async def get_album_by_id(self, album_id: str) -> AlbumDTO:
        """Get a specific album."""
        return await self.client.get_album(album_id)

    async def get_asset_by_id(self, asset_id: str) -> AssetDTO:
        """Get a specific asset."""
        return await self.client.get_asset(asset_id)

    def clear_cache(self) -> None:
        """Clear cached data (useful for testing)."""
        self._people_cache = None
        self._albums_cache = None
        self._assets_cache = None
