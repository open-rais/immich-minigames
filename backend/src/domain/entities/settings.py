from dataclasses import dataclass


@dataclass
class Settings:
    immich_url: str
    immich_api_key: str