"""Web Push DTOs - see services/notifications/."""

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
