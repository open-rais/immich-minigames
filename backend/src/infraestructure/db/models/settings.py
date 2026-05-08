from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SettingsModel(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )