"""Schedule schemas."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AvailabilitySlot(BaseModel):
    start: datetime
    end: datetime
    reason: str | None = None


class _BusinessHourBase(BaseModel):
    start_time_am: time | None = None
    end_time_am: time | None = None
    start_time_pm: time | None = None
    end_time_pm: time | None = None

    @model_validator(mode="after")
    def validate_slots(self) -> "_BusinessHourBase":
        for prefix in ("am", "pm"):
            start = getattr(self, f"start_time_{prefix}")
            end = getattr(self, f"end_time_{prefix}")
            if bool(start) ^ bool(end):
                raise ValueError(f"{prefix.upper()} slot requires both start and end")
            if start and end and start >= end:
                raise ValueError(f"{prefix.upper()} slot start_time must be before end_time")
        if not any(
            (
                self.start_time_am,
                self.end_time_am,
                self.start_time_pm,
                self.end_time_pm,
            )
        ):
            raise ValueError("At least one slot (AM or PM) must be provided")
        return self


class BusinessHourCreate(_BusinessHourBase):
    technician_id: str
    location_id: str
    day_of_week: int = Field(..., ge=0, le=6)


class BusinessHourUpdate(_BusinessHourBase):
    day_of_week: int | None = Field(None, ge=0, le=6)

    @model_validator(mode="after")
    def allow_partial(self) -> "BusinessHourUpdate":
        # Allow partial updates; skip parent validation if all slots are None.
        if all(
            slot is None
            for slot in (
                self.start_time_am,
                self.end_time_am,
                self.start_time_pm,
                self.end_time_pm,
            )
        ):
            return self
        return _BusinessHourBase.validate_slots(self)


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
