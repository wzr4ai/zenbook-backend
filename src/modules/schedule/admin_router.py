"""Admin schedule management routes."""

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

router = APIRouter(prefix="/api/v1/admin/schedule", tags=["admin-schedule"])


async def _ensure_unique_day(db: AsyncSession, item: BusinessHourCreate) -> None:
    stmt = select(BusinessHour).where(
        BusinessHour.technician_id == item.technician_id,
        BusinessHour.location_id == item.location_id,
        BusinessHour.day_of_week == item.day_of_week,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Business hour already defined for this day")


def _validate_record(record: BusinessHour) -> None:
    has_am = bool(record.start_time_am and record.end_time_am)
    has_pm = bool(record.start_time_pm and record.end_time_pm)
    if not (has_am or has_pm):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one slot must be configured")


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
        await _ensure_unique_day(db, item)
        record = BusinessHour(**item.model_dump())
        _validate_record(record)
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
    for field, value in update_data.items():
        setattr(rule, field, value)
    _validate_record(rule)
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
