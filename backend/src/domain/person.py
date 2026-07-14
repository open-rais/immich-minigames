"""Corresponds to Immich people."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class Person:
    id: UUID
    name: str
    birth_date: date | None
    asset_count: int
