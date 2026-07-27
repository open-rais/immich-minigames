"""Generic to_dict()/from_dict() for the frozen-dataclass "snapshot" types every game uses to
freeze a person/face's data into a round's JSONB payload (games/*.py's EntitySnapshot, HiddenFace,
etc.) - each used to hand-rewrite the same UUID-to-str/date-to-isoformat round trip, one field at a
time, which is exactly the kind of repetition that's easy to get subtly wrong (a forgotten None
check, a typo'd key) as a new game gets added. DictCodec infers the conversion from each field's own
type annotation instead."""

import types
from dataclasses import fields
from datetime import date
from typing import Any, TypeVar
from uuid import UUID

_T = TypeVar("_T", bound="DictCodec")


def _unwrap_optional(type_: Any) -> Any:
    """`X | None` -> `X` (leaves anything else, including a plain `X`, unchanged)."""
    if isinstance(type_, types.UnionType):
        non_none = [arg for arg in type_.__args__ if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return type_


def _encode(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _decode(value: Any, type_: Any) -> Any:
    if value is None:
        return None
    type_ = _unwrap_optional(type_)
    if type_ is UUID:
        return UUID(value)
    if type_ is date:
        return date.fromisoformat(value)
    return value


class DictCodec:
    """Mixin for a frozen dataclass whose fields are JSON primitives, UUID, or date (optionally
    `| None`) - to_dict()/from_dict() round-trip through that encoding, inferred from each field's
    type annotation, for storage in a round's JSONB payload column."""

    def to_dict(self) -> dict[str, Any]:
        return {f.name: _encode(getattr(self, f.name)) for f in fields(self)}

    @classmethod
    def from_dict(cls: type[_T], data: dict[str, Any]) -> _T:
        return cls(**{f.name: _decode(data[f.name], f.type) for f in fields(cls)})
