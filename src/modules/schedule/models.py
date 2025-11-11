"""Schedule ORM models."""

from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.models import TimestampMixin
from src.shared.ulid import generate_ulid
from src.shared.enums import Weekday, enum_values

WEEKDAY_VALUES = ", ".join(f"'{value}'" for value in enum_values(Weekday))

if TYPE_CHECKING:  # pragma: no cover
    from src.modules.catalog.models import Location
    from src.modules.users.models import Technician


class BusinessHour(Base, TimestampMixin):
    __tablename__ = "business_hours"
    __table_args__ = (
        UniqueConstraint("technician_id", "location_id", "rule_date", name="uq_business_hour_date"),
        CheckConstraint(
            f"day_of_week IN ({WEEKDAY_VALUES})",
            name="ck_business_hours_weekday",
        ),
    )

    rule_id: Mapped[str] = mapped_column(String(26), primary_key=True, default=generate_ulid)
    technician_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("technicians.technician_id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time_am: Mapped[time | None] = mapped_column(Time(timezone=True))
    end_time_am: Mapped[time | None] = mapped_column(Time(timezone=True))
    start_time_pm: Mapped[time | None] = mapped_column(Time(timezone=True))
    end_time_pm: Mapped[time | None] = mapped_column(Time(timezone=True))

    technician: Mapped["Technician"] = relationship(back_populates="business_hours")
    location: Mapped["Location"] = relationship(back_populates="business_hours")
