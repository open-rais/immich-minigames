from src.infraestructure.immich.client import ImmichHTTPClient
from src.infraestructure.immich.provider import ImmichProviderImpl
from src.domain.entities.settings import Settings


async def create_immich_provider(settings: Settings) -> ImmichProviderImpl:
    """Factory function to create Immich provider from settings.
    
    Args:
        settings: Settings entity with immich_url and immich_api_key
        
    Returns:
        Initialized ImmichProviderImpl
    """
    client = ImmichHTTPClient(
        base_url=settings.immich_url,
        api_key=settings.immich_api_key,
    )
    
    return ImmichProviderImpl(client)
