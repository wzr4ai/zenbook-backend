"""Shared enumerations used across modules."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Iterable, TypeVar

EnumType = TypeVar("EnumType", bound=StrEnum)


def enum_values(enum_cls: Iterable[EnumType]) -> list[str]:
    """Return the .value for each enum member (used by SQLAlchemy)."""
    return [member.value for member in enum_cls]


class UserRole(StrEnum):
    CUSTOMER = "customer"
    TECHNICIAN = "technician"
    ADMIN = "admin"


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Weekday(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @classmethod
    def from_index(cls, index: int) -> "Weekday":
        members = list(cls)
        if not 0 <= index < len(members):
            msg = f"weekday index {index} out of range"
            raise ValueError(msg)
        return members[index]

    @classmethod
    def from_date(cls, value: date) -> "Weekday":
        return cls.from_index(value.weekday())
