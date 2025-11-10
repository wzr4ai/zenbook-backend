"""Add explicit rule_date to business hours.

Revision ID: 9b7e1f2bb23c
Revises: 2d1f3f8c2e2b
Create Date: 2025-02-12 20:15:00.000000

"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b7e1f2bb23c"
down_revision: Union[str, Sequence[str], None] = "2d1f3f8c2e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("business_hours", sa.Column("rule_date", sa.Date(), nullable=True))
    bind = op.get_bind()
    business_hours = sa.table(
        "business_hours",
        sa.column("rule_id", sa.String(26)),
        sa.column("day_of_week", sa.Integer),
    )

    rows = list(bind.execute(sa.select(business_hours.c.rule_id, business_hours.c.day_of_week)))
    base_monday = date(2024, 1, 1)  # Monday reference
    for row in rows:
        computed = base_monday + timedelta(days=row.day_of_week)
        bind.execute(
            sa.text("UPDATE business_hours SET rule_date = :rule_date WHERE rule_id = :rule_id"),
            {"rule_id": row.rule_id, "rule_date": computed},
        )

    op.alter_column("business_hours", "rule_date", existing_type=sa.Date(), nullable=False)
    op.drop_constraint("uq_business_hour_day", "business_hours", type_="unique")
    op.create_unique_constraint(
        "uq_business_hour_date",
        "business_hours",
        ("technician_id", "location_id", "rule_date"),
    )


def downgrade() -> None:
    op.drop_constraint("uq_business_hour_date", "business_hours", type_="unique")
    op.create_unique_constraint(
        "uq_business_hour_day",
        "business_hours",
        ("technician_id", "location_id", "day_of_week"),
    )
    op.drop_column("business_hours", "rule_date")
