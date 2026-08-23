"""Web Push endpoints: per-account preferences, device subscriptions, and a manual test send.
Mounted under /notifications by api/api.py. See services/notifications/."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from api.auth_api import get_current_user
from api.deps import get_notifications_service
from api.dto.notifications import (
    NotificationPreferencesIn,
    NotificationPreferencesOut,
    SetLanguageIn,
    SubscribeIn,
    UnsubscribeIn,
)
from api.rate_limit import PUSH_SUBSCRIBE_LIMIT, PUSH_TEST_LIMIT, limiter
from persistence.users import UserModel
from services.notifications import NotificationPreferences, NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_preferences_out(prefs: NotificationPreferences) -> NotificationPreferencesOut:
    return NotificationPreferencesOut(
        daily_reminders=prefs.daily_reminders,
        birthdays=prefs.birthdays,
        album_anniversary=prefs.album_anniversary,
        language=prefs.language,
    )


@router.get("/preferences", response_model=NotificationPreferencesOut)
def get_preferences(
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> NotificationPreferencesOut:
    prefs = notifications_service.get_preferences(user.id)
    return _to_preferences_out(prefs)


@router.put("/preferences", response_model=NotificationPreferencesOut)
def update_preferences(
    body: NotificationPreferencesIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> NotificationPreferencesOut:
    prefs = notifications_service.update_preferences(user.id, NotificationPreferences(**body.model_dump()))
    return _to_preferences_out(prefs)


@router.patch("/preferences/language", response_model=NotificationPreferencesOut)
def set_language(
    body: SetLanguageIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> NotificationPreferencesOut:
    prefs = notifications_service.set_language(user.id, body.language)
    return _to_preferences_out(prefs)


@router.post("/subscriptions", status_code=204, response_model=None)
@limiter.limit(PUSH_SUBSCRIBE_LIMIT)
def add_subscription(
    request: Request,
    body: SubscribeIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> None:
    notifications_service.add_subscription(user.id, body.endpoint, body.keys.p256dh, body.keys.auth)


@router.delete("/subscriptions", status_code=204, response_model=None)
def remove_subscription(
    body: UnsubscribeIn,
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> None:
    notifications_service.remove_subscription(user.id, body.endpoint)


@router.post("/test", status_code=204, response_model=None)
@limiter.limit(PUSH_TEST_LIMIT)
def send_test(
    request: Request,
    user: Annotated[UserModel, Depends(get_current_user)],
    notifications_service: Annotated[NotificationService, Depends(get_notifications_service)],
) -> None:
    notifications_service.send_test(user.id)
