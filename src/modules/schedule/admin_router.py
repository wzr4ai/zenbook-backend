"""Admin schedule management routes."""

from datetime import date, time
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import require_admin
from src.modules.schedule.models import BusinessHour, ScheduleException
from src.modules.schedule.schemas import (
    BusinessHourCreate,
    BusinessHourPublic,
    BusinessHourUpdate,
    ScheduleExceptionCreate,
    ScheduleExceptionPublic,
    ScheduleExceptionUpdate,
)
from src.modules.users.models import User
from src.shared.enums import Weekday

router = APIRouter(prefix="/api/v1/admin/schedule", tags=["admin-schedule"])


async def _ensure_unique_date(
    db: AsyncSession,
    technician_id: str,
    location_id: str,
    rule_date: date,
    exclude_rule_id: str | None = None,
) -> None:
    stmt = select(BusinessHour).where(
        BusinessHour.technician_id == technician_id,
        BusinessHour.location_id == location_id,
        BusinessHour.rule_date == rule_date,
    )
    if exclude_rule_id:
        stmt = stmt.where(BusinessHour.rule_id != exclude_rule_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Business hour already defined for this date")


def _collect_intervals(record: BusinessHour) -> list[tuple[time, time]]:
    intervals: list[tuple[time, time]] = []
    for prefix in ("am", "pm"):
        start = getattr(record, f"start_time_{prefix}")
        end = getattr(record, f"end_time_{prefix}")
        if start and end:
            intervals.append((start, end))
    return intervals


def _has_overlap(intervals_a: Iterable[tuple[time, time]], intervals_b: Iterable[tuple[time, time]]) -> bool:
    for start_a, end_a in intervals_a:
        for start_b, end_b in intervals_b:
            if max(start_a, start_b) < min(end_a, end_b):
                return True
    return False


async def _ensure_no_cross_location_overlap(
    db: AsyncSession,
    candidate: BusinessHour,
    exclude_rule_id: str | None = None,
) -> None:
    stmt = select(BusinessHour).where(
        BusinessHour.technician_id == candidate.technician_id,
        BusinessHour.rule_date == candidate.rule_date,
    )
    if exclude_rule_id:
        stmt = stmt.where(BusinessHour.rule_id != exclude_rule_id)
    existing_rules = (await db.execute(stmt)).scalars().all()
    candidate_intervals = _collect_intervals(candidate)
    if not candidate_intervals:
        return
    for rule in existing_rules:
        if rule.location_id == candidate.location_id:
            continue
        if _has_overlap(candidate_intervals, _collect_intervals(rule)):
            message = "Technician already scheduled for an overlapping slot at another location"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _validate_record(record: BusinessHour) -> None:
    has_am = bool(record.start_time_am and record.end_time_am)
    has_pm = bool(record.start_time_pm and record.end_time_pm)
    if not (has_am or has_pm):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one slot must be configured")
    if record.rule_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rule_date is required")


async def _get_schedule_entity(db: AsyncSession, model, column, identifier: str, not_found: str):
    stmt = select(model).where(column == identifier)
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
    return entity


@router.post("/business-hours", response_model=list[BusinessHourPublic], status_code=status.HTTP_201_CREATED)
async def create_business_hours(
    payload: list[BusinessHourCreate],
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessHourPublic]:
    records: list[BusinessHour] = []
    for item in payload:
        await _ensure_unique_date(db, item.technician_id, item.location_id, item.rule_date)
        data = item.model_dump()
        data["day_of_week"] = Weekday.from_date(item.rule_date).value
        record = BusinessHour(**data)
        _validate_record(record)
        await _ensure_no_cross_location_overlap(db, record)
        db.add(record)
        records.append(record)
    await db.commit()
    for record in records:
        await db.refresh(record)
    return [BusinessHourPublic.model_validate(record) for record in records]


@router.get("/business-hours", response_model=list[BusinessHourPublic])
async def list_business_hours(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessHourPublic]:
    result = await db.execute(select(BusinessHour))
    return [BusinessHourPublic.model_validate(row) for row in result.scalars().all()]


@router.put("/business-hours/{rule_id}", response_model=BusinessHourPublic)
async def update_business_hour(
    rule_id: str,
    payload: BusinessHourUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BusinessHourPublic:
    rule = await _get_schedule_entity(db, BusinessHour, BusinessHour.rule_id, rule_id, "Business hour not found")
    update_data = payload.model_dump(exclude_unset=True)
    if "rule_date" in update_data and update_data["rule_date"] is not None:
        await _ensure_unique_date(
            db,
            rule.technician_id,
            rule.location_id,
            update_data["rule_date"],
            exclude_rule_id=rule.rule_id,
        )
        update_data["day_of_week"] = Weekday.from_date(update_data["rule_date"]).value
    for field, value in update_data.items():
        setattr(rule, field, value)
    _validate_record(rule)
    await _ensure_no_cross_location_overlap(db, rule, exclude_rule_id=rule.rule_id)
    await db.commit()
    await db.refresh(rule)
    return BusinessHourPublic.model_validate(rule)


@router.delete("/business-hours/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_hour(
    rule_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _get_schedule_entity(db, BusinessHour, BusinessHour.rule_id, rule_id, "Business hour not found")
    await db.delete(rule)
    await db.commit()


@router.post("/exceptions", response_model=ScheduleExceptionPublic, status_code=status.HTTP_201_CREATED)
async def create_exception(
    payload: ScheduleExceptionCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduleExceptionPublic:
    record = ScheduleException(**payload.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return ScheduleExceptionPublic.model_validate(record)


@router.get("/exceptions", response_model=list[ScheduleExceptionPublic])
async def list_exceptions(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduleExceptionPublic]:
    result = await db.execute(select(ScheduleException))
    return [ScheduleExceptionPublic.model_validate(row) for row in result.scalars().all()]


@router.put("/exceptions/{exception_id}", response_model=ScheduleExceptionPublic)
async def update_exception(
    exception_id: str,
    payload: ScheduleExceptionUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ScheduleExceptionPublic:
    exception = await _get_schedule_entity(
        db,
        ScheduleException,
        ScheduleException.exception_id,
        exception_id,
        "Schedule exception not found",
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(exception, field, value)
    await db.commit()
    await db.refresh(exception)
    return ScheduleExceptionPublic.model_validate(exception)


@router.delete("/exceptions/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exception(
    exception_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    exception = await _get_schedule_entity(
        db,
        ScheduleException,
        ScheduleException.exception_id,
        exception_id,
        "Schedule exception not found",
    )
    await db.delete(exception)
    await db.commit()
