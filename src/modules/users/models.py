"""ORM models for the users domain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.enums import UserRole, enum_values
from src.shared.models import TimestampMixin
from src.shared.ulid import generate_ulid

if TYPE_CHECKING:  # pragma: no cover - typing only
    from src.modules.appointments.models import Appointment
    from src.modules.catalog.models import Offering
    from src.modules.schedule.models import BusinessHour, ScheduleException


class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        default=generate_ulid,
    )
    wechat_openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=enum_values,
            validate_strings=True,
            name="userrole",
        ),
        nullable=False,
        default=UserRole.CUSTOMER,
    )
    display_name: Mapped[str | None] = mapped_column(String(100))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patients: Mapped[list[Patient]] = relationship(back_populates="manager")
    technician_profile: Mapped[Technician | None] = relationship(back_populates="user", uselist=False)


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("managed_by_user_id", "full_name", name="uq_patient_name_per_user"),)

    patient_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    managed_by_user_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    birth_date: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(String(255))

    manager: Mapped[User] = relationship(back_populates="patients")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient", cascade="all,delete-orphan")


class Technician(Base, TimestampMixin):
    __tablename__ = "technicians"

    technician_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    user_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    restricted_by_quota: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="technician_profile")
    offerings: Mapped[list[Offering]] = relationship(back_populates="technician")
    business_hours: Mapped[list[BusinessHour]] = relationship(back_populates="technician")
    exceptions: Mapped[list[ScheduleException]] = relationship(back_populates="technician")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="technician")


# Late imports for type-checking relationship targets.
from src.modules.appointments.models import Appointment  # noqa: E402
from src.modules.catalog.models import Offering  # noqa: E402
from src.modules.schedule.models import BusinessHour, ScheduleException  # noqa: E402
