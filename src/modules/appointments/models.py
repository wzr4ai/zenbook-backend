"""Appointment ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.enums import AppointmentStatus, UserRole, enum_values
from src.shared.models import TimestampMixin
from src.shared.ulid import generate_ulid

if TYPE_CHECKING:  # pragma: no cover
    from src.modules.catalog.models import Offering
    from src.modules.users.models import Patient, Technician, User


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_technician_start", "technician_id", "start_time"),
        CheckConstraint("end_time > start_time", name="ck_appointments_time_order"),
    )

    appointment_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    patient_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("patients.patient_id", ondelete="CASCADE"),
        nullable=False,
    )
    booked_by_user_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    offering_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("offerings.offering_id", ondelete="RESTRICT"),
        nullable=False,
    )
    technician_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("technicians.technician_id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            values_callable=enum_values,
            validate_strings=True,
            name="appointmentstatus",
        ),
        default=AppointmentStatus.SCHEDULED,
    )
    booked_by_role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=enum_values,
            validate_strings=True,
            name="userrole",
        ),
        nullable=False,
    )
    price_at_booking: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    booking_user: Mapped[User | None] = relationship()
    offering: Mapped[Offering] = relationship(back_populates="appointments")
    technician: Mapped[Technician] = relationship(back_populates="appointments")
