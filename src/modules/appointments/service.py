"""Appointment service layer."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.modules.appointments.models import Appointment
from src.modules.appointments.schemas import AppointmentAdminCreate, AppointmentCreate, AppointmentUpdate
from src.modules.catalog.models import Offering
from src.modules.schedule.service import AvailabilityRequest, get_availability
from src.modules.users.models import Patient, User
from src.shared.enums import AppointmentStatus, UserRole


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tz = ZoneInfo(settings.default_timezone)

    def _now(self) -> datetime:
        return datetime.now(tz=self.tz)

    async def create_customer(self, payload: AppointmentCreate, user: User) -> Appointment:
        patient = await self._get_patient(payload.patient_id, owner_id=user.user_id)
        offering = await self._get_offering(payload.offering_id)
        start = self._normalize_datetime(payload.start_time)
        duration = timedelta(minutes=offering.duration_minutes)
        await self._ensure_customer_slot(offering, start, duration)

        appointment = Appointment(
            patient_id=patient.patient_id,
            offering_id=offering.offering_id,
            technician_id=offering.technician_id,
            start_time=start,
            end_time=start + duration,
            price_at_booking=offering.price,
            notes=payload.notes,
            booked_by_user_id=user.user_id,
            booked_by_role=UserRole.CUSTOMER,
        )
        appointment.patient = patient
        appointment.offering = offering
        appointment.technician = offering.technician
        self.db.add(appointment)
        if user.default_location_id != offering.location_id:
            user.default_location_id = offering.location_id
        await self.db.commit()
        await self.db.refresh(appointment)
        appointment.patient = patient
        appointment.offering = offering
        appointment.technician = offering.technician
        return appointment

    async def list_for_user(self, user: User) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.technician),
                selectinload(Appointment.offering).selectinload(Offering.service),
                selectinload(Appointment.offering).selectinload(Offering.location),
            )
            .join(Patient)
            .where(Patient.managed_by_user_id == user.user_id)
            .order_by(Appointment.start_time.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_for_user(self, appointment_id: str, user: User) -> None:
        appointment = await self._get_user_appointment(appointment_id, user)
        if self._localize(appointment.start_time) <= self._now():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Appointment already started")
        await self.db.delete(appointment)
        await self.db.commit()

    async def admin_list(self) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.technician),
                selectinload(Appointment.offering).selectinload(Offering.service),
                selectinload(Appointment.offering).selectinload(Offering.location),
            )
            .order_by(Appointment.start_time.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def admin_create(self, payload: AppointmentAdminCreate, user: User) -> Appointment:
        patient = await self._get_patient(payload.patient_id)
        offering = await self._get_offering(payload.offering_id)
        start = self._normalize_datetime(payload.start_time)
        duration_minutes = payload.duration_override_minutes or offering.duration_minutes
        duration = timedelta(minutes=duration_minutes)
        await self._ensure_conflict_free(offering, start, start + duration)

        price = payload.price_override if payload.price_override is not None else offering.price
        appointment = Appointment(
            patient_id=patient.patient_id,
            offering_id=offering.offering_id,
            technician_id=offering.technician_id,
            start_time=start,
            end_time=start + duration,
            price_at_booking=price,
            notes=payload.notes,
            booked_by_user_id=user.user_id,
            booked_by_role=user.role,
        )
        appointment.patient = patient
        appointment.offering = offering
        appointment.technician = offering.technician
        self.db.add(appointment)
        await self.db.commit()
        await self.db.refresh(appointment)
        appointment.patient = patient
        appointment.offering = offering
        appointment.technician = offering.technician
        return appointment

    async def admin_update(self, appointment_id: str, payload: AppointmentUpdate) -> Appointment:
        appointment = await self._get_by_id(appointment_id)
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return appointment

        if "start_time" in update_data:
            new_start = self._normalize_datetime(update_data["start_time"])
            duration = appointment.end_time - appointment.start_time
            new_end = new_start + duration
            await self._ensure_conflict_free(
                appointment.offering,
                new_start,
                new_end,
                ignore_appointment_id=appointment.appointment_id,
            )
            appointment.start_time = new_start
            appointment.end_time = new_end

        if "status" in update_data:
            new_status: AppointmentStatus = update_data["status"]
            if self._localize(appointment.start_time) > self._now():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update status before appointment time",
                )
            if new_status not in {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status update")
            appointment.status = new_status
        if "notes" in update_data:
            appointment.notes = update_data["notes"]

        await self.db.commit()
        return await self._get_by_id(appointment.appointment_id)

    async def admin_delete(self, appointment_id: str) -> None:
        appointment = await self._get_by_id(appointment_id)
        await self.db.delete(appointment)
        await self.db.commit()

    async def _get_patient(self, patient_id: str, owner_id: str | None = None) -> Patient:
        stmt = select(Patient).where(Patient.patient_id == patient_id)
        if owner_id:
            stmt = stmt.where(Patient.managed_by_user_id == owner_id)
        result = await self.db.execute(stmt)
        patient = result.scalar_one_or_none()
        if patient is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return patient

    async def _get_offering(self, offering_id: str) -> Offering:
        stmt = (
            select(Offering)
            .options(
                selectinload(Offering.service),
                selectinload(Offering.technician),
                selectinload(Offering.location),
            )
            .where(Offering.offering_id == offering_id)
        )
        result = await self.db.execute(stmt)
        offering = result.scalar_one_or_none()
        if offering is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found")
        return offering

    async def _get_user_appointment(self, appointment_id: str, user: User) -> Appointment:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.technician),
                selectinload(Appointment.offering).selectinload(Offering.service),
                selectinload(Appointment.offering).selectinload(Offering.location),
            )
            .join(Patient)
            .where(
                Appointment.appointment_id == appointment_id,
                Patient.managed_by_user_id == user.user_id,
            )
        )
        result = await self.db.execute(stmt)
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        return appointment

    async def _get_by_id(self, appointment_id: str) -> Appointment:
        stmt = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.technician),
                selectinload(Appointment.offering).selectinload(Offering.service),
                selectinload(Appointment.offering).selectinload(Offering.location),
            )
            .where(Appointment.appointment_id == appointment_id)
        )
        result = await self.db.execute(stmt)
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
        return appointment

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Datetime must be timezone-aware")
        return value.astimezone(self.tz)

    def _localize(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=self.tz)
        return value.astimezone(self.tz)

    async def _ensure_customer_slot(self, offering: Offering, start: datetime, duration: timedelta) -> None:
        request = AvailabilityRequest(
            target_date=start.date(),
            technician_id=offering.technician_id,
            service_id=offering.service_id,
            location_id=offering.location_id,
            requester_role=UserRole.CUSTOMER,
        )
        slots = await get_availability(request, self.db)
        target_end = start + duration
        for slot in slots:
            if slot.reason is None and slot.start == start and slot.end == target_end:
                return
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested slot unavailable")

    async def _ensure_conflict_free(
        self,
        offering: Offering,
        start: datetime,
        end: datetime,
        ignore_appointment_id: str | None = None,
    ) -> None:
        stmt = (
            select(func.count(Appointment.appointment_id))
            .where(
                Appointment.technician_id == offering.technician_id,
                Appointment.status == AppointmentStatus.SCHEDULED,
                Appointment.start_time < end,
                Appointment.end_time > start,
            )
        )
        if ignore_appointment_id:
            stmt = stmt.where(Appointment.appointment_id != ignore_appointment_id)
        result = await self.db.execute(stmt)
        overlap_count = result.scalar_one()
        if overlap_count >= offering.service.concurrency_level:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already occupied")
