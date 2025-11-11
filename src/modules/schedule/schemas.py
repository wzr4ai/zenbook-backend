"""Schedule schemas."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.shared.enums import Weekday


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
        return self


class BusinessHourCreate(_BusinessHourBase):
    technician_id: str
    location_id: str
    rule_date: date

    @model_validator(mode="after")
    def ensure_slot_exists(self) -> "BusinessHourCreate":
        if not any((self.start_time_am, self.end_time_am, self.start_time_pm, self.end_time_pm)):
            raise ValueError("At least one slot (AM or PM) must be provided")
        return self


class BusinessHourUpdate(_BusinessHourBase):
    rule_date: date | None = None

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
    day_of_week: Weekday

