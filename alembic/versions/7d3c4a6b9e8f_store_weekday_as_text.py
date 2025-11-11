"""Store business hour weekday as text labels.

Revision ID: 7d3c4a6b9e8f
Revises: 5f6c0b7b8f2c
Create Date: 2025-02-14 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d3c4a6b9e8f"
down_revision: Union[str, Sequence[str], None] = "9b7e1f2bb23c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WEEKDAY_VALUES = "'monday','tuesday','wednesday','thursday','friday','saturday','sunday'"
WEEKDAY_CASE = """
    CASE day_of_week
        WHEN 0 THEN 'monday'
        WHEN 1 THEN 'tuesday'
        WHEN 2 THEN 'wednesday'
        WHEN 3 THEN 'thursday'
        WHEN 4 THEN 'friday'
        WHEN 5 THEN 'saturday'
        WHEN 6 THEN 'sunday'
    END
"""
WEEKDAY_REVERSE_CASE = """
    CASE day_of_week
        WHEN 'monday' THEN 0
        WHEN 'tuesday' THEN 1
        WHEN 'wednesday' THEN 2
        WHEN 'thursday' THEN 3
        WHEN 'friday' THEN 4
        WHEN 'saturday' THEN 5
        WHEN 'sunday' THEN 6
    END
"""


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_checks = {check["name"] for check in inspector.get_check_constraints("business_hours")}
    if "ck_business_hours_dow" in existing_checks:
        op.drop_constraint("ck_business_hours_dow", "business_hours", type_="check")

    op.add_column("business_hours", sa.Column("day_of_week_text", sa.String(16), nullable=True))
    op.execute(
        f"""
        UPDATE business_hours
        SET day_of_week_text = {WEEKDAY_CASE}
        """
    )
    op.alter_column("business_hours", "day_of_week_text", existing_type=sa.String(16), nullable=False)
    op.drop_column("business_hours", "day_of_week")
    op.alter_column(
        "business_hours",
        "day_of_week_text",
        new_column_name="day_of_week",
        existing_type=sa.String(16),
        nullable=False,
    )

    op.create_check_constraint(
        "ck_business_hours_weekday",
        "business_hours",
        f"day_of_week IN ({WEEKDAY_VALUES})",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_checks = {check["name"] for check in inspector.get_check_constraints("business_hours")}
    if "ck_business_hours_weekday" in existing_checks:
        op.drop_constraint("ck_business_hours_weekday", "business_hours", type_="check")

    op.add_column("business_hours", sa.Column("day_of_week_int", sa.Integer(), nullable=True))
    op.execute(
        f"""
        UPDATE business_hours
        SET day_of_week_int = {WEEKDAY_REVERSE_CASE}
        """
    )
    op.alter_column("business_hours", "day_of_week_int", existing_type=sa.Integer(), nullable=False)
    op.drop_column("business_hours", "day_of_week")
    op.alter_column(
        "business_hours",
        "day_of_week_int",
        new_column_name="day_of_week",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_check_constraint("ck_business_hours_dow", "business_hours", "day_of_week BETWEEN 0 AND 6")
