"""Business logic for computing availability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.modules.appointments.models import Appointment
from src.modules.catalog.models import Offering, Service
from src.modules.schedule.models import BusinessHour
from src.modules.schedule.schemas import AvailabilitySlot
from src.modules.users.models import Technician
from src.shared.enums import AppointmentStatus, UserRole, Weekday

UNAVAILABLE_REASON_CONFLICT = "已被预约"
UNAVAILABLE_REASON_QUOTA = "客户配额已满"


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
    raw_slots = _build_slots_from_rules(business_hours, request.target_date, duration, tz)
    if not raw_slots:
        return []

    appointments = await _get_appointments_for_day(technician.technician_id, day_start, day_end, db)
    noon = day_start.replace(hour=12, minute=0, second=0, microsecond=0)
    availability = _evaluate_slot_reasons(
        raw_slots,
        appointments,
        service.concurrency_level,
        blocked_morning,
        blocked_afternoon,
        noon,
    )
    return availability


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
    weekday_value = Weekday.from_date(request.target_date).value
    stmt = select(BusinessHour).where(
        BusinessHour.technician_id == request.technician_id,
        BusinessHour.location_id == request.location_id,
        or_(
            BusinessHour.rule_date == request.target_date,
            and_(
                BusinessHour.rule_date.is_(None),
                BusinessHour.day_of_week == weekday_value,
            ),
        ),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
        if rule.start_time_am and rule.end_time_am:
            start_am = _combine(target_date, rule.start_time_am, tz)
            end_am = _combine(target_date, rule.end_time_am, tz)
            slots.extend(_generate_slots(start_am, end_am, duration))
        if rule.start_time_pm and rule.end_time_pm:
            start_pm = _combine(target_date, rule.start_time_pm, tz)
            end_pm = _combine(target_date, rule.end_time_pm, tz)
            slots.extend(_generate_slots(start_pm, end_pm, duration))
    return slots


def _generate_slots(start: datetime, end: datetime, duration: timedelta) -> list[tuple[datetime, datetime]]:
    slots: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor + duration <= end:
        slots.append((cursor, cursor + duration))
        cursor += duration
    return slots


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


def _evaluate_slot_reasons(
    slots: list[tuple[datetime, datetime]],
    appointments: list[Appointment],
    concurrency_level: int,
    blocked_morning: bool,
    blocked_afternoon: bool,
    noon: datetime,
) -> list[AvailabilitySlot]:
    quota_mask = [
        (blocked_morning and start < noon) or (blocked_afternoon and start >= noon) for start, _ in slots
    ]
    unconstrained_slots = [slot for slot, masked in zip(slots, quota_mask) if not masked]
    available_after_conflicts = _filter_by_concurrency(unconstrained_slots, appointments, concurrency_level)
    available_set = {slot for slot in available_after_conflicts}

    annotated: list[AvailabilitySlot] = []
    for slot, masked in zip(slots, quota_mask):
        start, end = slot
        if masked:
            reason = UNAVAILABLE_REASON_QUOTA
        elif slot not in available_set:
            reason = UNAVAILABLE_REASON_CONFLICT
        else:
            reason = None
        annotated.append(AvailabilitySlot(start=start, end=end, reason=reason))
    return annotated


def _overlaps(
    slot_a: tuple[datetime, datetime],
    slot_b: tuple[datetime, datetime],
) -> bool:
    start_a, end_a = slot_a
    start_b, end_b = slot_b
    return start_a < end_b and end_a > start_b
