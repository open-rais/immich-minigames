"""Web Push DTOs - see services/notifications/."""

from typing import Literal

from pydantic import BaseModel


class NotificationPreferencesOut(BaseModel):
    daily_reminders: bool
    birthdays: bool
    album_anniversary: bool
    language: str


class NotificationPreferencesIn(BaseModel):
    daily_reminders: bool
    birthdays: bool
    album_anniversary: bool
    language: str


class SetLanguageIn(BaseModel):
    # A literal (not services/notifications/messages.py's own language keys, kept in sync by hand
    # - same "duplicated on purpose" convention that module's own docstring already documents) so
    # FastAPI turns anything else into a 422 on its own, no manual validation needed.
    language: Literal["en", "es", "fr", "de"]


class PushSubscriptionKeysIn(BaseModel):
    p256dh: str
    auth: str


class SubscribeIn(BaseModel):
    """Matches the browser's own `PushSubscription.toJSON()` shape (minus `expirationTime`, which
    this app never reads) so the frontend can send it close to as-is."""

    endpoint: str
    keys: PushSubscriptionKeysIn


class UnsubscribeIn(BaseModel):
    endpoint: str
