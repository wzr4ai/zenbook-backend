"""Shared enumerations used across modules."""

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
