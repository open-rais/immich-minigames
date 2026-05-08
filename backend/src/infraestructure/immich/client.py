import httpx
from typing import Any

from src.infraestructure.immich.schemas import (
    PersonDTO,
    AlbumDTO,
    AssetDTO,
    ImmichHealthDTO,
)


class ImmichAPIError(Exception):
    """Custom exception for Immich API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ImmichHTTPClient:
    """Low-level HTTP client for Immich API.
    
    Handles authentication, retries, and error handling.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Immich HTTP client.
        
        Args:
            base_url: Base URL of Immich server (e.g., http://immich.example.com)
            api_key: Immich API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.base_url}/api{path}"

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            **kwargs: Additional arguments for httpx request
            
        Returns:
            JSON response as dict
            
        Raises:
            ImmichAPIError: If request fails
        """
        url = self._build_url(path)
        headers = self._get_headers()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs,
                    )

                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 401:
                        raise ImmichAPIError("Unauthorized. Check API key.", 401)
                    elif response.status_code == 404:
                        raise ImmichAPIError("Resource not found.", 404)
                    elif response.status_code >= 500:
                        # Retry on server errors
                        if attempt < self.max_retries - 1:
                            continue
                        raise ImmichAPIError(
                            f"Server error: {response.status_code}",
                            response.status_code,
                        )
                    else:
                        raise ImmichAPIError(
                            f"HTTP {response.status_code}: {response.text}",
                            response.status_code,
                        )

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    continue
                raise ImmichAPIError("Request timeout")
            except httpx.ConnectError as e:
                raise ImmichAPIError(f"Connection error: {str(e)}")
            except ImmichAPIError:
                raise
            except Exception as e:
                raise ImmichAPIError(f"Unexpected error: {str(e)}")

        raise ImmichAPIError("Max retries exceeded")

    async def get_health(self) -> ImmichHealthDTO:
        """Check Immich server health."""
        try:
            data = await self._request("GET", "/health")
            return ImmichHealthDTO(
                success=True,
                version=data.get("version", "unknown"),
            )
        except ImmichAPIError:
            raise

    async def list_people(self, limit: int = 100) -> list[PersonDTO]:
        """List people from Immich."""
        data = await self._request("GET", "/people", params={"withHidden": False})
        
        people = []
        for person in data.get("people", []):
            people.append(
                PersonDTO(
                    id=person["id"],
                    name=person.get("name", "Unknown"),
                    asset_count=person.get("assetCount", 0),
                )
            )
        
        return people[:limit]

    async def get_person(self, person_id: str) -> PersonDTO:
        """Get a specific person."""
        data = await self._request("GET", f"/people/{person_id}")
        
        return PersonDTO(
            id=data["id"],
            name=data.get("name", "Unknown"),
            asset_count=data.get("assetCount", 0),
        )

    async def list_albums(self, limit: int = 100) -> list[AlbumDTO]:
        """List albums from Immich."""
        data = await self._request("GET", "/albums")
        
        albums = []
        for album in data:
            albums.append(
                AlbumDTO(
                    id=album["id"],
                    album_name=album.get("albumName", "Unknown"),
                    asset_count=album.get("assetCount", 0),
                )
            )
        
        return albums[:limit]

    async def get_album(self, album_id: str) -> AlbumDTO:
        """Get a specific album."""
        data = await self._request("GET", f"/albums/{album_id}")
        
        return AlbumDTO(
            id=data["id"],
            album_name=data.get("albumName", "Unknown"),
            asset_count=data.get("assetCount", 0),
        )

    async def list_assets(self, limit: int = 1000) -> list[AssetDTO]:
        """List assets from Immich."""
        data = await self._request(
            "GET",
            "/search/metadata",
            params={"limit": limit},
        )
        
        assets = []
        for asset in data.get("assets", {}).get("items", []):
            assets.append(
                AssetDTO(
                    id=asset["id"],
                    file_created_at=asset.get("fileCreatedAt"),
                    file_modified_at=asset.get("fileModifiedAt"),
                    metadata=asset,
                )
            )
        
        return assets

    async def get_asset(self, asset_id: str) -> AssetDTO:
        """Get a specific asset."""
        data = await self._request("GET", f"/assets/{asset_id}")
        
        return AssetDTO(
            id=data["id"],
            file_created_at=data.get("fileCreatedAt"),
            file_modified_at=data.get("fileModifiedAt"),
            metadata=data,
        )
