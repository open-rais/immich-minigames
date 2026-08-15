"""Healthcheck DTO (GET /api/v1/health) - see api/api.py."""

from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok"]
