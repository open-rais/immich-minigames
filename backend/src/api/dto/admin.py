"""Admin-editable game settings DTOs - both the normal per-game_type ones (ADMIN-FEATURE.md point
#4, see games/settings_registry.py) and the daily-only ones (roadmap point #G, see
services/daily_settings.py), which share the same GameSettingOut shape. Also invitations (roadmap
#H, F1, see services/invite_service.py) - unrelated to game settings, just the same "admin-only
DTOs" module."""

from calendar import timegm
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from games.settings_spec import SettingSpec
from persistence.invites import InviteModel


class GameSettingOut(BaseModel):
    key: str
    value: float
    default: float
    value_type: Literal["int", "float"]
    min_value: float
    max_value: float


class GameSettingsOut(BaseModel):
    game_type: str
    mode: str
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, specs: list[SettingSpec], values: dict[str, float]
    ) -> "GameSettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


class DailySettingsOut(BaseModel):
    game_type: str
    mode: str
    # The "Activar juego diario" checkbox from roadmap #f - whether this mode is offered in the
    # daily rotation at all.
    enabled: bool
    settings: list[GameSettingOut]

    @classmethod
    def from_specs(
        cls, game_type: str, mode: str, enabled: bool, specs: list[SettingSpec], values: dict[str, float]
    ) -> "DailySettingsOut":
        return cls(
            game_type=game_type,
            mode=mode,
            enabled=enabled,
            settings=[
                GameSettingOut(
                    key=spec.key,
                    value=values[spec.key],
                    default=spec.default,
                    value_type=spec.value_type,
                    min_value=spec.min_value,
                    max_value=spec.max_value,
                )
                for spec in specs
            ],
        )


class UpdateDailySettingsIn(BaseModel):
    # PATCH semantics - omit a field to leave it unchanged (mirrors auth_schemas.py's
    # UpdateProfileIn), so toggling "enabled" from the admin UI doesn't require also restating
    # every setting value, and saving settings doesn't require also restating "enabled".
    enabled: bool | None = None
    values: dict[str, float] | None = None


class InviteOut(BaseModel):
    id: UUID
    kind: str
    # Derived, not stored - InviteModel only persists used_at/expires_at (see from_model below).
    status: Literal["pending", "used", "expired"]
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, invite: InviteModel) -> "InviteOut":
        if invite.used_at is not None:
            status: Literal["pending", "used", "expired"] = "used"
        # timegm(...utctimetuple()), not a plain `<` comparison - expires_at can round-trip through
        # the DB tz-naive or tz-aware depending on how the table was created (see
        # services/auth_service.py's get_user_from_token for the same issue with
        # password_changed_at) - utctimetuple() normalizes either case to a UTC epoch second,
        # avoiding a raised TypeError (naive vs aware) or a silently wrong answer (naive
        # misinterpreted as local time).
        elif timegm(invite.expires_at.utctimetuple()) < timegm(datetime.now(UTC).utctimetuple()):
            status = "expired"
        else:
            status = "pending"
        return cls(
            id=invite.id,
            kind=invite.kind,
            status=status,
            expires_at=invite.expires_at,
            used_at=invite.used_at,
            created_at=invite.created_at,
        )


class CreateInviteOut(BaseModel):
    id: UUID
    # The only time the plain token is ever available - see InviteService.create_invite.
    token: str
    expires_at: datetime
