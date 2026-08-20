"""
Own persistence layer for Web Push notifications (F2 of roadmap point O) - devices subscribed to
push, one row of per-account preferences, and (unused until the scheduler lands) a log of what's
already been sent, for idempotency. Shares this app's own database/Base with users.py/games.py
(persistence/base.py). Tables created by migration 0015.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import SCHEMA, Base


class PushSubscriptionModel(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = (Index("ix_push_subscriptions_user", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # ON DELETE CASCADE (unlike the rest of this app's FKs, which cascade ORM-side via
    # relationship(cascade=...)): a device row has no other owner to clean it up through, and a
    # stale endpoint left behind after an account is deleted is otherwise never noticed.
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"))
    # The push service URL - unique because it's the natural key of a subscribed device (a
    # reinstall or a cleared browser gets a new one). p256dh/auth are the client's encryption keys,
    # not secrets that decrypt anything (see services/notifications/sender.py).
    endpoint: Mapped[str] = mapped_column(unique=True)
    p256dh: Mapped[str]
    auth: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_success_at: Mapped[datetime | None] = mapped_column(default=None)
    # Diagnostic only - a 404/410 deletes the row outright (see sender.py); this just counts
    # transient (429/5xx) failures between successes.
    failure_count: Mapped[int] = mapped_column(default=0, server_default="0")


class NotificationPreferencesModel(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"), primary_key=True)
    # One flag for both the 10:00 "new daily" and 21:00 "streak at risk" reminders - they're
    # mutually exclusive per user by the scheduler's own rules, so a second toggle would always
    # leave one of the two permanently inert with no way to tell which.
    daily_reminders: Mapped[bool] = mapped_column(default=False, server_default="false")
    birthdays: Mapped[bool] = mapped_column(default=False, server_default="false")
    album_anniversary: Mapped[bool] = mapped_column(default=False, server_default="false")
    # The push payload is composed server-side (a closed app has no access to i18next/localStorage
    # to translate it), so the account's chosen language has to live here too.
    language: Mapped[str] = mapped_column(default="en", server_default="en")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class NotificationDeliveryModel(Base):
    """Idempotency log for the scheduler - not read or written anywhere yet. Created now because
    it shares migration 0015 with the two tables above rather than needing a second migration just
    for itself later."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (Index("uq_notification_deliveries", "user_id", "kind", "day", unique=True),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id"))
    kind: Mapped[str]
    day: Mapped[date]
    sent_at: Mapped[datetime] = mapped_column(server_default=func.now())
