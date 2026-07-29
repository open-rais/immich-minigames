"""Public runtime config DTO (ROUNDS-VIEW.md roadmap point #10, see Settings.immich_public_url)."""

from pydantic import BaseModel


class ConfigOut(BaseModel):
    # Settings.immich_public_url, already resolved (IMMICH_EXTERNAL_URL, a fallback to
    # IMMICH_SERVER_URL when unset, or None) - genuinely null in the response either when
    # IMMICH_EXTERNAL_URL is explicitly set empty (roadmap #H, F6 - "no public link", not a
    # fallback) or, in principle, if immich_server_url itself were ever blanked out.
    immich_external_url: str | None
