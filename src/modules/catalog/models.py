"""Catalog ORM models (locations, services, offerings)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.models import TimestampMixin
from src.shared.ulid import generate_ulid

if TYPE_CHECKING:  # pragma: no cover
    from src.modules.appointments.models import Appointment
    from src.modules.schedule.models import BusinessHour, ScheduleException
    from src.modules.users.models import Technician


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    location_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    offerings: Mapped[list["Offering"]] = relationship(back_populates="location")
    business_hours: Mapped[list["BusinessHour"]] = relationship(back_populates="location")
    exceptions: Mapped[list["ScheduleException"]] = relationship(back_populates="location")


class Service(Base, TimestampMixin):
    __tablename__ = "services"

    service_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    default_duration_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    concurrency_level: Mapped[int] = mapped_column(default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    offerings: Mapped[list["Offering"]] = relationship(back_populates="service")


class Offering(Base, TimestampMixin):
    __tablename__ = "offerings"
    __table_args__ = (
        UniqueConstraint("technician_id", "service_id", "location_id", name="uq_offering_combo"),
        CheckConstraint("price >= 0", name="ck_offering_price_positive"),
        CheckConstraint("duration_minutes > 0", name="ck_offering_duration_positive"),
    )

    offering_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    technician_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("technicians.technician_id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("services.service_id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    technician: Mapped["Technician"] = relationship(back_populates="offerings")
    service: Mapped["Service"] = relationship(back_populates="offerings")
    location: Mapped["Location"] = relationship(back_populates="offerings")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="offering")
