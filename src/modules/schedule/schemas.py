"""Schedule schemas."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class AvailabilitySlot(BaseModel):
    start: datetime
    end: datetime
    reason: str | None = None


class BusinessHourCreate(BaseModel):
    technician_id: str
    location_id: str
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time


class BusinessHourUpdate(BaseModel):
    day_of_week: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None


class BusinessHourPublic(BusinessHourCreate):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str


class ScheduleExceptionCreate(BaseModel):
    technician_id: str
    location_id: str
    date: date
    is_available: bool = False
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = None


class ScheduleExceptionUpdate(BaseModel):
    is_available: bool | None = None
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = None


class ScheduleExceptionPublic(ScheduleExceptionCreate):
    model_config = ConfigDict(from_attributes=True)

    exception_id: str
