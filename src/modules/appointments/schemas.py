"""Appointments schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.shared.enums import AppointmentStatus, UserRole


class AppointmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: str = Field(serialization_alias="id")
    patient_id: str
    offering_id: str
    technician_id: str
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    booked_by_role: UserRole
    price_at_booking: Decimal
    notes: str | None = None


class AppointmentCreate(BaseModel):
    offering_id: str
    patient_id: str
    start_time: datetime
    notes: str | None = None


class AppointmentAdminCreate(AppointmentCreate):
    price_override: Decimal | None = None
    duration_override_minutes: int | None = Field(None, gt=0)


class AppointmentUpdate(BaseModel):
    start_time: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = None
