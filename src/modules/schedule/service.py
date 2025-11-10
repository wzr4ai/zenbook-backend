"""Business logic for computing availability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.modules.appointments.models import Appointment
from src.modules.catalog.models import Offering, Service
from src.modules.schedule.models import BusinessHour, ScheduleException
from src.modules.schedule.schemas import AvailabilitySlot
from src.modules.users.models import Technician
from src.shared.enums import AppointmentStatus, UserRole


@dataclass
class AvailabilityRequest:
    target_date: date
    technician_id: str
    service_id: str
    location_id: str
    requester_role: UserRole


async def get_availability(request: AvailabilityRequest, db: AsyncSession) -> list[AvailabilitySlot]:
    offering = await _get_offering(request, db)
    if offering is None or not offering.is_available:
        return []

    technician = offering.technician
    service = offering.service
    tz = ZoneInfo(settings.default_timezone)

    day_start = datetime.combine(request.target_date, time.min, tz)
    day_end = day_start + timedelta(days=1)

    morning_quota_limit, afternoon_quota_limit = _resolve_quota_limits(technician)
    blocked_morning = blocked_afternoon = False
    if request.requester_role == UserRole.CUSTOMER and (morning_quota_limit > 0 or afternoon_quota_limit > 0):
        blocked_morning, blocked_afternoon = await _quota_overages(
            technician.technician_id, day_start, day_end, morning_quota_limit, afternoon_quota_limit, db
        )

    duration = timedelta(minutes=offering.duration_minutes)
    business_hours = await _get_business_hours(request, db)
    exception = await _get_exception(request, db)

    slots = _build_slots_from_rules(business_hours, request.target_date, duration, tz)
    slots = _apply_exception(slots, exception, request.target_date, duration, tz)

    if blocked_morning or blocked_afternoon:
        noon = day_start.replace(hour=12, minute=0, second=0, microsecond=0)
        if blocked_morning:
            slots = [slot for slot in slots if slot[0] >= noon]
        if blocked_afternoon:
            slots = [slot for slot in slots if slot[0] < noon]

    if not slots:
        return []

    appointments = await _get_appointments_for_day(technician.technician_id, day_start, day_end, db)
    slots = _filter_by_concurrency(slots, appointments, service.concurrency_level)
    return [AvailabilitySlot(start=start, end=end) for start, end in slots]


async def _quota_overages(
    technician_id: str,
    day_start: datetime,
    day_end: datetime,
    morning_quota_limit: int,
    afternoon_quota_limit: int,
    db: AsyncSession,
) -> tuple[bool, bool]:
    morning_end = day_start.replace(hour=12, minute=0, second=0, microsecond=0)

    morning_full = False
    afternoon_full = False

    if morning_quota_limit > 0:
        morning_count = await _count_customer_appointments(technician_id, day_start, morning_end, db)
        morning_full = morning_count >= morning_quota_limit

    if afternoon_quota_limit > 0:
        afternoon_count = await _count_customer_appointments(technician_id, morning_end, day_end, db)
        afternoon_full = afternoon_count >= afternoon_quota_limit

    return morning_full, afternoon_full


async def _count_customer_appointments(
    technician_id: str,
    start_time: datetime,
    end_time: datetime,
    db: AsyncSession,
) -> int:
    stmt = (
        select(func.count(Appointment.appointment_id))
        .where(
            Appointment.technician_id == technician_id,
            Appointment.booked_by_role == UserRole.CUSTOMER,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_time >= start_time,
            Appointment.start_time < end_time,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def _get_offering(request: AvailabilityRequest, db: AsyncSession) -> Offering | None:
    stmt = (
        select(Offering)
        .options(selectinload(Offering.service), selectinload(Offering.technician))
        .where(
            Offering.technician_id == request.technician_id,
            Offering.service_id == request.service_id,
            Offering.location_id == request.location_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_business_hours(request: AvailabilityRequest, db: AsyncSession) -> list[BusinessHour]:
    stmt = (
        select(BusinessHour)
        .where(
            BusinessHour.technician_id == request.technician_id,
            BusinessHour.location_id == request.location_id,
            BusinessHour.day_of_week == request.target_date.weekday(),
        )
        .order_by(BusinessHour.start_time)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_exception(request: AvailabilityRequest, db: AsyncSession) -> ScheduleException | None:
    stmt = select(ScheduleException).where(
        ScheduleException.technician_id == request.technician_id,
        ScheduleException.location_id == request.location_id,
        ScheduleException.date == request.target_date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _combine(dt_date: date, value: time, tz: ZoneInfo) -> datetime:
    combined = datetime.combine(dt_date, value.replace(tzinfo=None))
    if value.tzinfo:
        return combined.replace(tzinfo=value.tzinfo).astimezone(tz)
    return combined.replace(tzinfo=tz)


def _build_slots_from_rules(
    rules: list[BusinessHour],
    target_date: date,
    duration: timedelta,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    slots: list[tuple[datetime, datetime]] = []
    for rule in rules:
        start = _combine(target_date, rule.start_time, tz)
        end = _combine(target_date, rule.end_time, tz)
        slots.extend(_generate_slots(start, end, duration))
    return slots


def _generate_slots(start: datetime, end: datetime, duration: timedelta) -> list[tuple[datetime, datetime]]:
    slots: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor + duration <= end:
        slots.append((cursor, cursor + duration))
        cursor += duration
    return slots


def _apply_exception(
    slots: list[tuple[datetime, datetime]],
    exception: ScheduleException | None,
    target_date: date,
    duration: timedelta,
    tz: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    if exception is None:
        return sorted(slots, key=lambda s: s[0])

    exc_start = _combine(target_date, exception.start_time, tz) if exception.start_time else None
    exc_end = _combine(target_date, exception.end_time, tz) if exception.end_time else None

    if not exception.is_available:
        if exc_start and exc_end:
            slots = [slot for slot in slots if not _overlaps(slot, (exc_start, exc_end))]
            return sorted(slots, key=lambda s: s[0])
        return []

    if exc_start and exc_end:
        extra = _generate_slots(exc_start, exc_end, duration)
        slots.extend(extra)
    return sorted({slot[0]: slot for slot in slots}.values(), key=lambda s: s[0])


def _overlaps(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


async def _get_appointments_for_day(
    technician_id: str,
    day_start: datetime,
    day_end: datetime,
    db: AsyncSession,
) -> list[Appointment]:
    stmt = (
        select(Appointment)
        .where(
            Appointment.technician_id == technician_id,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.start_time < day_end,
            Appointment.end_time > day_start,
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _resolve_quota_limits(technician: Technician) -> tuple[int, int]:
    base_morning = settings.father_customer_morning_quota if technician.restricted_by_quota else 0
    base_afternoon = settings.father_customer_afternoon_quota if technician.restricted_by_quota else 0
    morning_limit = _normalize_quota(technician.morning_quota_limit, base_morning)
    afternoon_limit = _normalize_quota(technician.afternoon_quota_limit, base_afternoon)
    return morning_limit, afternoon_limit


def _normalize_quota(explicit: int | None, fallback: int) -> int:
    if explicit is None:
        return max(0, fallback)
    return max(0, explicit)


def _normalize_timezone(value: datetime, target_tz: tzinfo | None) -> datetime:
    if target_tz is None:
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=target_tz)
    return value.astimezone(target_tz)


def _filter_by_concurrency(
    slots: list[tuple[datetime, datetime]],
    appointments: list[Appointment],
    concurrency_level: int,
) -> list[tuple[datetime, datetime]]:
    filtered: list[tuple[datetime, datetime]] = []
    for start, end in slots:
        overlaps = sum(
            1
            for appt in appointments
            if _overlaps(
                (start, end),
                (
                    _normalize_timezone(appt.start_time, start.tzinfo),
                    _normalize_timezone(appt.end_time, end.tzinfo),
                ),
            )
        )
        if overlaps < concurrency_level:
            filtered.append((start, end))
    return filtered
