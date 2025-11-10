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

    daily_quota_limit, weekly_quota_limit = _resolve_quota_limits(technician)
    if request.requester_role == UserRole.CUSTOMER and (daily_quota_limit > 0 or weekly_quota_limit > 0):
        if await _quota_exceeded(
            technician.technician_id, day_start, day_end, daily_quota_limit, weekly_quota_limit, db
        ):
            return []

    duration = timedelta(minutes=offering.duration_minutes)
    business_hours = await _get_business_hours(request, db)
    exception = await _get_exception(request, db)

    slots = _build_slots_from_rules(business_hours, request.target_date, duration, tz)
    slots = _apply_exception(slots, exception, request.target_date, duration, tz)

    if not slots:
        return []

    appointments = await _get_appointments_for_day(technician.technician_id, day_start, day_end, db)
    slots = _filter_by_concurrency(slots, appointments, service.concurrency_level)
    return [AvailabilitySlot(start=start, end=end) for start, end in slots]


async def _quota_exceeded(
    technician_id: str,
    day_start: datetime,
    day_end: datetime,
    daily_quota_limit: int,
    weekly_quota_limit: int,
    db: AsyncSession,
) -> bool:
    if daily_quota_limit > 0:
        day_count = await _count_customer_appointments(technician_id, day_start, day_end, db)
        if day_count >= daily_quota_limit:
            return True

    if weekly_quota_limit > 0:
        week_start = day_start - timedelta(days=day_start.weekday())
        week_end = week_start + timedelta(days=7)
        week_count = await _count_customer_appointments(technician_id, week_start, week_end, db)
        if week_count >= weekly_quota_limit:
            return True

    return False


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
    base_daily = settings.father_customer_daily_quota if technician.restricted_by_quota else 0
    base_weekly = settings.father_customer_weekly_quota if technician.restricted_by_quota else 0
    daily_limit = _normalize_quota(technician.daily_quota_limit, base_daily)
    weekly_limit = _normalize_quota(technician.weekly_quota_limit, base_weekly)
    return daily_limit, weekly_limit


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
