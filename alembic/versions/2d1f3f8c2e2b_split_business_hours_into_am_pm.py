"""Split business hours into AM/PM slots per day.

Revision ID: 2d1f3f8c2e2b
Revises: 5f6c0b7b8f2c
Create Date: 2025-02-12 14:30:00.000000

"""
from __future__ import annotations

from datetime import time
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2d1f3f8c2e2b"
down_revision: Union[str, Sequence[str], None] = "5f6c0b7b8f2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_hours", sa.Column("start_time_am", sa.Time(timezone=True), nullable=True))
    op.add_column("business_hours", sa.Column("end_time_am", sa.Time(timezone=True), nullable=True))
    op.add_column("business_hours", sa.Column("start_time_pm", sa.Time(timezone=True), nullable=True))
    op.add_column("business_hours", sa.Column("end_time_pm", sa.Time(timezone=True), nullable=True))

    bind = op.get_bind()
    business_hours = sa.table(
        "business_hours",
        sa.column("rule_id", sa.String(26)),
        sa.column("technician_id", sa.String(26)),
        sa.column("location_id", sa.String(26)),
        sa.column("day_of_week", sa.Integer),
        sa.column("start_time", sa.Time(timezone=True)),
        sa.column("end_time", sa.Time(timezone=True)),
        sa.column("start_time_am", sa.Time(timezone=True)),
        sa.column("end_time_am", sa.Time(timezone=True)),
        sa.column("start_time_pm", sa.Time(timezone=True)),
        sa.column("end_time_pm", sa.Time(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    rows = list(
        bind.execute(
            sa.select(
                business_hours.c.rule_id,
                business_hours.c.technician_id,
                business_hours.c.location_id,
                business_hours.c.day_of_week,
                business_hours.c.start_time,
                business_hours.c.end_time,
                business_hours.c.created_at,
                business_hours.c.updated_at,
            )
        )
    )

    midday = time(13, 0)
    grouped: dict[tuple[str, str, int], dict[str, object]] = {}
    for row in rows:
        key = (row.technician_id, row.location_id, row.day_of_week)
        payload = grouped.setdefault(
            key,
            {
                "rule_id": row.rule_id,
                "technician_id": row.technician_id,
                "location_id": row.location_id,
                "day_of_week": row.day_of_week,
                "start_time_am": None,
                "end_time_am": None,
                "start_time_pm": None,
                "end_time_pm": None,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        )
        payload["created_at"] = min(payload["created_at"], row.created_at) if payload["created_at"] else row.created_at
        payload["updated_at"] = max(payload["updated_at"], row.updated_at) if payload["updated_at"] else row.updated_at
        target = "am" if row.start_time < midday else "pm"
        start_key = f"start_time_{target}"
        end_key = f"end_time_{target}"
        if payload[start_key] is not None:
            # Keep the earliest slot for duplicates within the same half-day.
            continue
        payload[start_key] = row.start_time
        payload[end_key] = row.end_time

    bind.execute(sa.text("DELETE FROM business_hours"))
    for payload in grouped.values():
        bind.execute(
            sa.text(
                """
                INSERT INTO business_hours (
                    rule_id, technician_id, location_id, day_of_week,
                    start_time_am, end_time_am, start_time_pm, end_time_pm,
                    created_at, updated_at
                ) VALUES (
                    :rule_id, :technician_id, :location_id, :day_of_week,
                    :start_time_am, :end_time_am, :start_time_pm, :end_time_pm,
                    :created_at, :updated_at
                )
                """
            ),
            payload,
        )

    op.drop_constraint("uq_business_hour_slot", "business_hours", type_="unique")
    op.drop_column("business_hours", "end_time")
    op.drop_column("business_hours", "start_time")
    op.create_unique_constraint(
        "uq_business_hour_day",
        "business_hours",
        ("technician_id", "location_id", "day_of_week"),
    )


def downgrade() -> None:
    op.add_column("business_hours", sa.Column("start_time", sa.Time(timezone=True), nullable=False))
    op.add_column("business_hours", sa.Column("end_time", sa.Time(timezone=True), nullable=False))
    op.drop_constraint("uq_business_hour_day", "business_hours", type_="unique")

    bind = op.get_bind()
    business_hours = sa.table(
        "business_hours",
        sa.column("rule_id", sa.String(26)),
        sa.column("technician_id", sa.String(26)),
        sa.column("location_id", sa.String(26)),
        sa.column("day_of_week", sa.Integer),
        sa.column("start_time_am", sa.Time(timezone=True)),
        sa.column("end_time_am", sa.Time(timezone=True)),
        sa.column("start_time_pm", sa.Time(timezone=True)),
        sa.column("end_time_pm", sa.Time(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    rows = list(bind.execute(sa.select(business_hours)).mappings())
    bind.execute(sa.text("DELETE FROM business_hours"))
    for row in rows:
        for label in ("am", "pm"):
            start = row[f"start_time_{label}"]
            end = row[f"end_time_{label}"]
            if start is None or end is None:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO business_hours (
                        rule_id, technician_id, location_id, day_of_week,
                        start_time, end_time, created_at, updated_at
                    ) VALUES (
                        :rule_id, :technician_id, :location_id, :day_of_week,
                        :start_time, :end_time, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "rule_id": row["rule_id"],
                    "technician_id": row["technician_id"],
                    "location_id": row["location_id"],
                    "day_of_week": row["day_of_week"],
                    "start_time": start,
                    "end_time": end,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                },
            )

    op.drop_column("business_hours", "end_time_pm")
    op.drop_column("business_hours", "start_time_pm")
    op.drop_column("business_hours", "end_time_am")
    op.drop_column("business_hours", "start_time_am")
    op.create_unique_constraint(
        "uq_business_hour_slot",
        "business_hours",
        ("technician_id", "location_id", "day_of_week", "start_time"),
    )
