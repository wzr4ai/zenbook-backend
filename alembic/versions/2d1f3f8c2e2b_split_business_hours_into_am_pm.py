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


def _get_existing_columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("business_hours")}


def _ensure_column(bind, name: str, column: sa.Column) -> None:
    if name not in _get_existing_columns(bind):
        op.add_column("business_hours", column)


def _drop_constraint_if_exists(bind, name: str, table: str, constraint_type: str = "unique") -> None:
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(table)
    if any(constraint["name"] == name for constraint in constraints):
        op.drop_constraint(name, table, type_=constraint_type)


def _create_unique_constraint_if_missing(bind, name: str, table: str, columns: tuple[str, ...]) -> None:
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(table)
    if any(constraint["name"] == name for constraint in constraints):
        return
    op.create_unique_constraint(name, table, columns)


def _ensure_index(bind, table: str, name: str, columns: tuple[str, ...]) -> None:
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if name in existing:
        return
    op.create_index(name, table, columns)


def upgrade() -> None:
    bind = op.get_bind()

    _ensure_column(bind, "start_time_am", sa.Column("start_time_am", sa.Time(timezone=True), nullable=True))
    _ensure_column(bind, "end_time_am", sa.Column("end_time_am", sa.Time(timezone=True), nullable=True))
    _ensure_column(bind, "start_time_pm", sa.Column("start_time_pm", sa.Time(timezone=True), nullable=True))
    _ensure_column(bind, "end_time_pm", sa.Column("end_time_pm", sa.Time(timezone=True), nullable=True))

    columns = _get_existing_columns(bind)
    legacy_columns_present = "start_time" in columns and "end_time" in columns

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

    if legacy_columns_present:
        _ensure_index(bind, "business_hours", "ix_business_hours_technician_id", ("technician_id",))
        _ensure_index(bind, "business_hours", "ix_business_hours_location_id", ("location_id",))
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
            payload["created_at"] = (
                min(payload["created_at"], row.created_at) if payload["created_at"] else row.created_at
            )
            payload["updated_at"] = (
                max(payload["updated_at"], row.updated_at) if payload["updated_at"] else row.updated_at
            )
            target = "am" if row.start_time < midday else "pm"
            start_key = f"start_time_{target}"
            end_key = f"end_time_{target}"
            if payload[start_key] is not None:
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

        _drop_constraint_if_exists(bind, "uq_business_hour_slot", "business_hours")
        if legacy_columns_present:
            op.drop_column("business_hours", "end_time")
            op.drop_column("business_hours", "start_time")

    _create_unique_constraint_if_missing(
        bind,
        "uq_business_hour_day",
        "business_hours",
        ("technician_id", "location_id", "day_of_week"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    _drop_constraint_if_exists(bind, "uq_business_hour_day", "business_hours")
    _ensure_column(bind, "start_time", sa.Column("start_time", sa.Time(timezone=True), nullable=False))
    _ensure_column(bind, "end_time", sa.Column("end_time", sa.Time(timezone=True), nullable=False))

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
            start = row.get(f"start_time_{label}")
            end = row.get(f"end_time_{label}")
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
    _create_unique_constraint_if_missing(
        bind,
        "uq_business_hour_slot",
        "business_hours",
        ("technician_id", "location_id", "day_of_week", "start_time"),
    )
