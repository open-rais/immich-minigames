"""The scheduler thread: ticks every 60s, decides (via schedule.py, on already-fetched data) what
to send this minute, and sends it (via NotificationService.send_to_user). Mirrors
services/embedding_jobs.py's thread/event shape, with one real difference from that precedent:
this one starts unconditionally at boot (main.py's lifespan) whenever push is configured at all,
rather than waiting for something to trigger it - a schedule not tied to any request.

Multi-process safety: pg_try_advisory_lock (non-blocking - a tick that can't get the lock just
skips this minute rather than queuing behind another process) with its own text-key namespace
("notif-tick", distinct from daily_challenge_service.py's "daily:..." keys, so hashtextextended
can never collide the two locks). Unlike daily_challenge_service.py's pg_advisory_xact_lock (
transaction-scoped, auto-released on commit), pg_try_advisory_lock is session-scoped - it has to be
released explicitly with pg_advisory_unlock before the session's connection goes back to the pool,
or a pooled connection would carry the lock into whatever unrelated session reuses it next.

Restart safety: notification_deliveries' unique (user_id, kind, day) index, INSERT ... ON CONFLICT
DO NOTHING before sending - a tick that re-processes a day already delivered (a restart mid-grace-
window) finds every user already marked and sends nothing twice.
"""

import logging
import threading
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from config import Settings
from persistence.games_repository import GameRepository
from persistence.notifications import NotificationDeliveryModel, NotificationPreferencesModel, PushSubscriptionModel
from services.daily_challenge_service import DailyChallengeService
from services.daily_games_service import DailyGamesService
from services.daily_settings import DailySettingsService
from services.game_factory import GameFactory
from services.game_settings_service import GameSettingsService
from services.immich import ImmichService
from services.ml_service import MLService
from services.notifications import NotificationService, content, messages, schedule
from services.reports_service import ReportsService

logger = logging.getLogger(__name__)

TICK_INTERVAL_SECONDS = 60
# Distinct namespace from daily_challenge_service.py's "daily:{challenge_date}:{game_type}:{mode}"
# keys - any string works as long as it can never collide with that prefix.
_LOCK_KEY_TEXT = "notif-tick"
# notification_deliveries exists purely for idempotency, not history - nothing ever reads a row
# older than "today", so this just keeps the table from growing forever.
_DELIVERY_RETENTION_DAYS = 30


def _seconds_until_midnight(now: datetime) -> int:
    """None of the four notifications say anything true past the server's own midnight ("today"
    changes meaning), so the push service should give up and drop it there instead of delivering
    something misleading to a device that reconnects tomorrow."""
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return max(0, int((tomorrow - now).total_seconds()))


def _candidate_user_ids(session: Session, preference_flag) -> list[UUID]:
    """Users with the given notification_preferences flag on AND at least one subscribed device -
    a preference with zero devices, or a device whose owner never touched preferences (still
    False by default), has nothing to receive anyway."""
    stmt = (
        select(NotificationPreferencesModel.user_id)
        .join(PushSubscriptionModel, PushSubscriptionModel.user_id == NotificationPreferencesModel.user_id)
        .where(preference_flag.is_(True))
        .distinct()
    )
    return list(session.scalars(stmt))


def _mark_delivered(session: Session, user_id: UUID, kind: str, today: date) -> bool:
    """True if this is the first delivery of (user_id, kind, today) - False means some earlier
    tick (this process or another) already sent it, so the caller must not send again.

    Checks via RETURNING, not rowcount - an INSERT ... ON CONFLICT DO NOTHING reports rowcount as
    -1 (this driver's "not available" sentinel) whether or not the conflict actually happened,
    which would make this always look like the caller should skip sending. RETURNING has no such
    ambiguity: a skipped insert returns zero rows, a real one returns the row it inserted."""
    stmt = (
        pg_insert(NotificationDeliveryModel)
        .values(id=uuid4(), user_id=user_id, kind=kind, day=today)
        .on_conflict_do_nothing(index_elements=["user_id", "kind", "day"])
        .returning(NotificationDeliveryModel.id)
    )
    inserted_id = session.execute(stmt).scalar()
    session.commit()
    return inserted_id is not None


def _process_daily(
    session: Session,
    notification_service: NotificationService,
    daily_games_service: DailyGamesService,
    game_repository: GameRepository,
    now: datetime,
    active_kinds: list[str],
) -> None:
    want_available = "daily_available" in active_kinds
    want_reminder = "daily_reminder" in active_kinds
    if not want_available and not want_reminder:
        return

    today = now.date()
    user_ids = _candidate_user_ids(session, NotificationPreferencesModel.daily_reminders)
    if not user_ids:
        return

    # One query for every user and every mode's streak (through yesterday - see
    # schedule.decide_daily_notification's docstring for why yesterday, never today) instead of
    # one per user.
    streaks = game_repository.daily_streaks_by_mode(user_ids, today - timedelta(days=1))
    ttl = _seconds_until_midnight(now)

    for user_id in user_ids:
        try:
            statuses = daily_games_service.get_daily_status(user_id, today)
            enabled_modes = [(s.game_type, s.mode) for s in statuses]
            unfinished_modes = [(s.game_type, s.mode) for s in statuses if s.status != "finished"]
            user_streaks = {(gt, m): streaks.get((user_id, gt, m), 0) for gt, m in enabled_modes}

            decision = schedule.decide_daily_notification(enabled_modes, unfinished_modes, user_streaks)
            if decision is None:
                continue
            if decision.kind == "daily_available" and not want_available:
                continue
            if decision.kind == "daily_reminder" and not want_reminder:
                continue

            if not _mark_delivered(session, user_id, decision.kind, today):
                continue

            preferences = notification_service.get_preferences(user_id)
            if decision.kind == "daily_available":
                message = messages.daily_available(preferences.language)
            elif decision.variant == "streak_at_risk":
                message = messages.daily_reminder_streak_at_risk(
                    preferences.language, decision.game_type, decision.streak
                )
            else:
                message = messages.daily_reminder_generic(preferences.language)

            notification_service.send_to_user(
                user_id, title=message.title, body=message.body, url="/", tag=decision.kind, ttl=ttl
            )
        except Exception:
            logger.exception("daily notification failed for user %s", user_id)


def _process_installation_wide(
    session: Session,
    notification_service: NotificationService,
    now: datetime,
    kind: str,
    preference_flag,
    build_message,
) -> None:
    """Shared shape for birthdays and album_anniversary - both compute one piece of content ONCE
    (not per user, unlike the daily reminder) and fan the same message out to every candidate
    user, in their own language."""
    today = now.date()
    user_ids = _candidate_user_ids(session, preference_flag)
    if not user_ids:
        return
    ttl = _seconds_until_midnight(now)
    for user_id in user_ids:
        try:
            if not _mark_delivered(session, user_id, kind, today):
                continue
            preferences = notification_service.get_preferences(user_id)
            message = build_message(preferences.language)
            notification_service.send_to_user(
                user_id, title=message.title, body=message.body, url="/", tag=kind, ttl=ttl
            )
        except Exception:
            logger.exception("%s notification failed for user %s", kind, user_id)


def _prune_old_deliveries(session: Session, today: date) -> None:
    cutoff = today - timedelta(days=_DELIVERY_RETENTION_DAYS)
    session.execute(delete(NotificationDeliveryModel).where(NotificationDeliveryModel.day < cutoff))
    session.commit()


def run_tick(
    session: Session,
    settings: Settings,
    immich_service: ImmichService,
    ml_service: MLService,
    now: datetime,
) -> None:
    """One tick's worth of work, already inside the advisory lock - never called directly except
    by _locked_tick (below) and tests, which don't need the lock dance."""
    active_kinds = schedule.active_kinds_for_tick(now)
    if not active_kinds:
        return
    today = now.date()

    notification_service = NotificationService(session, settings)
    reports_service = ReportsService(session)
    game_repository = GameRepository(session)
    game_factory = GameFactory(session, immich_service, ml_service, GameSettingsService(session), reports_service)
    daily_settings_service = DailySettingsService(session)
    daily_challenge_service = DailyChallengeService(session, immich_service, reports_service)
    daily_games_service = DailyGamesService(
        game_repository, game_factory, daily_settings_service, daily_challenge_service
    )

    if "daily_available" in active_kinds or "daily_reminder" in active_kinds:
        _process_daily(session, notification_service, daily_games_service, game_repository, now, active_kinds)

    if "birthdays" in active_kinds:
        entries = content.todays_birthdays(immich_service, reports_service, today)
        if entries:
            _process_installation_wide(
                session,
                notification_service,
                now,
                "birthdays",
                NotificationPreferencesModel.birthdays,
                lambda language: messages.birthdays(language, entries),
            )

    if "album_anniversary" in active_kinds:
        album_entries = content.todays_album_anniversaries(immich_service, today)
        if album_entries:
            _process_installation_wide(
                session,
                notification_service,
                now,
                "album_anniversary",
                NotificationPreferencesModel.album_anniversary,
                lambda language: messages.album_anniversary(language, album_entries),
            )

    _prune_old_deliveries(session, today)


def _locked_tick(
    session_factory: sessionmaker,
    settings: Settings,
    immich_service: ImmichService,
    ml_service: MLService,
    now: datetime,
) -> None:
    session = session_factory()
    try:
        lock_key = func.hashtextextended(_LOCK_KEY_TEXT, 0)
        acquired = session.execute(select(func.pg_try_advisory_lock(lock_key))).scalar()
        if not acquired:
            return
        try:
            run_tick(session, settings, immich_service, ml_service, now)
        finally:
            # Explicit unlock, same session that acquired it - pg_try_advisory_lock is session-
            # scoped, not transaction-scoped, so skipping this would leave the lock held by
            # whatever connection this session's underlying connection becomes once returned to
            # the pool, until that pooled connection happens to close outright.
            session.execute(select(func.pg_advisory_unlock(lock_key)))
    finally:
        session.close()


class NotificationRunner:
    def __init__(
        self,
        session_factory: sessionmaker,
        settings: Settings,
        immich_service: ImmichService,
        ml_service: MLService,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._immich_service = immich_service
        self._ml_service = ml_service
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """No-op if already running, and if push isn't configured at all - starting a thread that
        would just fail every send is worse than not starting one (see PushNotConfiguredError)."""
        if self._thread is not None or not self._settings.push_enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="notification-scheduler")
        self._thread.start()
        # Every log line's own timestamp prefix is UTC (logging_setup.py's formatters always
        # convert to UTC for display) - this scheduler compares against the server's own *local*
        # time instead (whatever TZ the process/container has, e.g. America/Santiago is UTC-4).
        # Stated explicitly here because that gap is easy to hit while hand-testing a slot time
        # off a log timestamp: reading "00:20" from a log line and setting a slot to "00:20"
        # silently means something 4 hours away from what was intended.
        logger.info("notification scheduler started - comparing against local time %s, not UTC", datetime.now())

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_tick_now()
            except Exception:
                logger.exception("notification tick crashed")
            # Event.wait, not time.sleep - wakes immediately on shutdown() instead of finishing
            # out up to 60s of a sleep nobody needs anymore.
            self._stop_event.wait(TICK_INTERVAL_SECONDS)

    def run_tick_now(self, now: datetime | None = None) -> None:
        """The real tick, and also what api/admin_notifications_api.py's force-tick test endpoint
        calls directly with an explicit `now` - simulating any time of day without touching the
        system clock."""
        # Naive datetime.now() - the server's own local time (a single TZ per installation, from
        # the process/container's TZ env var), never UTC and never tz-aware (schedule.py's
        # SLOT_TIMES/comparisons are naive throughout).
        _locked_tick(
            self._session_factory, self._settings, self._immich_service, self._ml_service, now or datetime.now()
        )

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
