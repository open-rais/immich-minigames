"""Admin promotion (ADMIN-FEATURE.md point #1) - run once per backend startup (see main.py's
startup event), not tied to any request. Promotion only: never creates an account, only flips
is_admin on one that already registered normally via AuthService.register."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import Settings
from persistence.users import UserModel

logger = logging.getLogger(__name__)


def ensure_admin(session: Session, settings: Settings) -> None:
    if not settings.admin_email:
        return

    user = session.scalar(select(UserModel).where(UserModel.email == settings.admin_email))
    if user is None:
        logger.warning(
            "ADMIN_EMAIL=%s does not match any registered account - register it via /signup, "
            "then restart the backend to promote it",
            settings.admin_email,
        )
        return

    if not user.is_admin:
        user.is_admin = True
        session.commit()
        logger.info("promoted %s to admin", settings.admin_email)
