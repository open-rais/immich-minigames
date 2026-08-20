"""
Wraps pywebpush. Two things beyond a straight passthrough:

1. `_NoRedirectSession` - pywebpush sends over `requests`, whose default (`allow_redirects=True`)
   would silently follow a 3xx response into wherever it points. That's the same SSRF surface
   `POST /notifications/subscriptions`'s allowlist (endpoint_safety.py) already closed at
   subscribe time, reopened one HTTP hop later - a malicious or compromised push service could
   redirect the actual send anywhere. Disabling redirects means such a response surfaces as an
   ordinary WebPushException instead of being followed.
2. Mapping 404/410 (Gone - the subscription is dead) apart from every other status: those two mean
   "delete this subscription", nothing else does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests
from pywebpush import WebPushException, webpush

from config import Settings


class PushNotConfiguredError(Exception):
    """Raised by send_push when VAPID keys aren't set - mapped to 503 by api/error_handlers.py."""


@dataclass(frozen=True)
class PushResult:
    ok: bool
    # True only for 404/410 - the caller should delete the subscription row. False for every other
    # failure (429/5xx/anything else), which is transient or unexpected but not proof the
    # subscription itself is dead.
    should_delete_subscription: bool
    status_code: int | None


class _NoRedirectSession(requests.Session):
    def request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        kwargs.setdefault("allow_redirects", False)
        return super().request(method, url, **kwargs)  # type: ignore[arg-type]


_session = _NoRedirectSession()

# A manual test ping shouldn't outlive the settings page that requested it - unlike the four
# scheduled notifications (§3.15's "TTL = seconds until server midnight" rule), which don't exist
# yet in this phase.
TEST_TTL_SECONDS = 60


def send_push(
    settings: Settings,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    title: str,
    body: str,
    url: str,
    tag: str,
    ttl: int = TEST_TTL_SECONDS,
) -> PushResult:
    if not settings.push_enabled:
        raise PushNotConfiguredError("VAPID keys are not configured")

    subscription_info = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_contact_email}"},
            ttl=ttl,
            headers={"Urgency": "normal"},
            requests_session=_session,
        )
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return PushResult(
            ok=False,
            should_delete_subscription=status_code in (404, 410),
            status_code=status_code,
        )

    return PushResult(ok=True, should_delete_subscription=False, status_code=None)
