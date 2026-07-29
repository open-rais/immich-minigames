"""Public runtime config DTO (ROUNDS-VIEW.md roadmap point #10, see Settings.immich_public_url)."""

from pydantic import BaseModel


class ConfigOut(BaseModel):
    # Settings.immich_public_url, already resolved (IMMICH_EXTERNAL_URL or a fallback to
    # IMMICH_SERVER_URL) - optional because immich_server_url is a plain str field with no
    # guarantee against being blanked out, not because callers are expected to see null in practice.
    immich_external_url: str | None
