"""Admin-only test hook for the notification scheduler (services/notifications/runner.py) - forces
one tick immediately, optionally simulating any time of day, so the four scheduled notifications
can be verified without waiting for their real slot or touching the system clock. Mounted under
/admin/notifications by api/api.py."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.admin_api import get_current_admin_user
from api.deps import get_notification_runner
from config import Settings, get_settings
from persistence.users import UserModel
from services.notifications.runner import NotificationRunner

router = APIRouter(prefix="/admin/notifications", tags=["admin"])


@router.post("/run-tick", status_code=204, response_model=None)
def run_tick(
    _admin: Annotated[UserModel, Depends(get_current_admin_user)],
    runner: Annotated[NotificationRunner, Depends(get_notification_runner)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[
        datetime | None,
        Query(description="Local server datetime to simulate, no timezone (e.g. 2026-08-20T21:05:00)"),
    ] = None,
) -> None:
    if not settings.push_enabled:
        raise HTTPException(status_code=503, detail="push is not configured")
    # schedule.py compares naive datetimes throughout (the server's own local time, no per-user
    # TZ) - stripping any offset a caller included keeps that assumption true regardless of what
    # they passed, rather than a TypeError from comparing naive and aware datetimes deep inside
    # run_tick.
    runner.run_tick_now(now.replace(tzinfo=None) if now else None)
