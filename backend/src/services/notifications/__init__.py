"""
Web Push facade (mirrors services/immich/ - one class re-exporting a package split by concern):
subscription/preference CRUD, a manual test send, and send_to_user - the per-device send-and-record
loop both the manual test and runner.py's scheduled deliveries share. content.py/schedule.py decide
*what*/*when*; runner.py orchestrates; this module is the only thing that actually touches
push_subscriptions rows.
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
from services.notifications.sender import TEST_TTL_SECONDS, send_push

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
        has_subscription = self._session.scalar(
            sa.select(PushSubscriptionModel.id).where(PushSubscriptionModel.user_id == user_id).limit(1)
        )
        if has_subscription is None:
            raise NoPushSubscriptionsError(f"user {user_id} has no push subscriptions")

        # Plain, non-localized copy - a manual debugging ping, not one of the four scheduled
        # notifications messages.py composes per-language content for.
        any_ok = self.send_to_user(
            user_id,
            title="Immich Minigames",
            body="Test notification - if you can see this, push is working.",
            url="/",
            tag="test",
        )
        if not any_ok:
            raise PushSendFailedError(f"push send failed for every subscription of user {user_id}")

    def send_to_user(
        self, user_id: UUID, *, title: str, body: str, url: str, tag: str, ttl: int = TEST_TTL_SECONDS
    ) -> bool:
        """Sends to every one of the user's subscribed devices, updating/deleting rows exactly
        like send_test always has - the only difference from calling send_test's old inline loop
        directly is this never raises, so runner.py's per-user scheduling loop can call this for
        many users in a row without one dead device aborting the rest of the tick. Returns whether
        at least one device received it; the caller decides what "none of them did" means for its
        own case (send_test turns it into PushSendFailedError, runner.py just logs and moves on)."""
        subscriptions = list(
            self._session.scalars(sa.select(PushSubscriptionModel).where(PushSubscriptionModel.user_id == user_id))
        )
        any_ok = False
        for subscription in subscriptions:
            result = send_push(
                self._settings,
                endpoint=subscription.endpoint,
                p256dh=subscription.p256dh,
                auth=subscription.auth,
                title=title,
                body=body,
                url=url,
                tag=tag,
                ttl=ttl,
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
                audit("push_send_failed", user_id=str(user_id), status_code=result.status_code)
        self._session.commit()
        return any_ok
