"""
Web Push facade (mirrors services/immich/ - one class re-exporting a package split by concern):
subscription/preference CRUD plus a manual test send. The actual content/scheduling of the four
real notifications (messages.py/content.py/schedule.py/runner.py in the doc this feature was
planned from) lands in a later phase - this one is the pipe, not what flows through it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from audit import audit
from config import Settings
from persistence.notifications import NotificationPreferencesModel, PushSubscriptionModel
from services.notifications.endpoint_safety import validate_push_endpoint
from services.notifications.sender import send_push

__all__ = ["NotificationPreferences", "NotificationService", "NoPushSubscriptionsError", "PushSendFailedError"]


class NoPushSubscriptionsError(Exception):
    """Raised by send_test when the account has no subscribed devices - mapped to 404."""


class PushSendFailedError(Exception):
    """Raised by send_test when every one of the account's subscriptions failed to receive the
    push - mapped to 502. Distinct from NoPushSubscriptionsError (no devices at all) and
    PushNotConfiguredError (no VAPID keys) - this means the send was attempted and the push
    service rejected it (or was unreachable) for all of them."""


@dataclass(frozen=True)
class NotificationPreferences:
    daily_reminders: bool
    birthdays: bool
    album_anniversary: bool
    language: str


_DEFAULT_PREFERENCES = NotificationPreferences(
    daily_reminders=False, birthdays=False, album_anniversary=False, language="en"
)


class NotificationService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def get_preferences(self, user_id: UUID) -> NotificationPreferences:
        """No row yet just means "every default" - the row itself is created lazily, on the first
        PUT (update_preferences), not here."""
        row = self._session.get(NotificationPreferencesModel, user_id)
        if row is None:
            return _DEFAULT_PREFERENCES
        return NotificationPreferences(
            daily_reminders=row.daily_reminders,
            birthdays=row.birthdays,
            album_anniversary=row.album_anniversary,
            language=row.language,
        )

    def update_preferences(self, user_id: UUID, preferences: NotificationPreferences) -> NotificationPreferences:
        stmt = (
            pg_insert(NotificationPreferencesModel)
            .values(
                user_id=user_id,
                daily_reminders=preferences.daily_reminders,
                birthdays=preferences.birthdays,
                album_anniversary=preferences.album_anniversary,
                language=preferences.language,
                updated_at=sa.func.now(),
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "daily_reminders": preferences.daily_reminders,
                    "birthdays": preferences.birthdays,
                    "album_anniversary": preferences.album_anniversary,
                    "language": preferences.language,
                    "updated_at": sa.func.now(),
                },
            )
        )
        self._session.execute(stmt)
        self._session.commit()
        return preferences

    def add_subscription(self, user_id: UUID, endpoint: str, p256dh: str, auth: str) -> None:
        """Idempotent by endpoint - resubscribing (e.g. every app load calling subscribe() again)
        just refreshes the same row instead of accumulating duplicates. Raises
        PushEndpointRejectedError (services/notifications/endpoint_safety.py) before touching the
        DB if the endpoint fails the SSRF allowlist/private-IP check."""
        validate_push_endpoint(endpoint, self._settings)

        stmt = (
            pg_insert(PushSubscriptionModel)
            .values(id=uuid4(), user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
            .on_conflict_do_update(
                index_elements=["endpoint"],
                set_={"user_id": user_id, "p256dh": p256dh, "auth": auth, "failure_count": 0},
            )
        )
        self._session.execute(stmt)
        self._session.commit()
        audit("push_subscription_added", user_id=str(user_id))

    def remove_subscription(self, user_id: UUID, endpoint: str) -> None:
        """Scoped to user_id as well as endpoint - a user can never unsubscribe a device that
        isn't theirs by guessing/replaying someone else's endpoint."""
        stmt = sa.delete(PushSubscriptionModel).where(
            PushSubscriptionModel.user_id == user_id, PushSubscriptionModel.endpoint == endpoint
        )
        self._session.execute(stmt)
        self._session.commit()
        audit("push_subscription_removed", user_id=str(user_id))

    def send_test(self, user_id: UUID) -> None:
        subscriptions = list(
            self._session.scalars(sa.select(PushSubscriptionModel).where(PushSubscriptionModel.user_id == user_id))
        )
        if not subscriptions:
            raise NoPushSubscriptionsError(f"user {user_id} has no push subscriptions")

        # Plain, non-localized copy - the real per-language content (services/notifications/
        # messages.py in the design this was planned from) belongs to the four scheduled
        # notifications, not a manual test ping.
        any_ok = False
        last_status: int | None = None
        for subscription in subscriptions:
            result = send_push(
                self._settings,
                endpoint=subscription.endpoint,
                p256dh=subscription.p256dh,
                auth=subscription.auth,
                title="Immich Minigames",
                body="Test notification - if you can see this, push is working.",
                url="/",
                tag="test",
            )
            if result.ok:
                any_ok = True
                subscription.last_success_at = datetime.now(UTC)
                subscription.failure_count = 0
            elif result.should_delete_subscription:
                self._session.delete(subscription)
                audit("push_subscription_expired", user_id=str(user_id), status_code=result.status_code)
            else:
                subscription.failure_count += 1
                last_status = result.status_code
                audit("push_send_failed", user_id=str(user_id), status_code=result.status_code)
        self._session.commit()

        if not any_ok:
            raise PushSendFailedError(f"push send failed for every subscription (last status: {last_status})")
