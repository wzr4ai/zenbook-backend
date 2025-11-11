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
down_revision: Union[str, Sequence[str], None] = "5f6c0b7b8f2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WEEKDAY_VALUES = "'monday','tuesday','wednesday','thursday','friday','saturday','sunday'"


def upgrade() -> None:
    op.drop_constraint("ck_business_hours_dow", "business_hours", type_="check")

    op.execute(
        f"""
        ALTER TABLE business_hours
        ALTER COLUMN day_of_week TYPE VARCHAR(16)
        USING (
            ARRAY[{WEEKDAY_VALUES}][day_of_week + 1]
        )
        """
    )

    op.create_check_constraint(
        "ck_business_hours_weekday",
        "business_hours",
        f"day_of_week IN ({WEEKDAY_VALUES})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_business_hours_weekday", "business_hours", type_="check")

    op.execute(
        f"""
        ALTER TABLE business_hours
        ALTER COLUMN day_of_week TYPE INTEGER
        USING (
            array_position(ARRAY[{WEEKDAY_VALUES}], day_of_week) - 1
        )
        """
    )

    op.create_check_constraint("ck_business_hours_dow", "business_hours", "day_of_week BETWEEN 0 AND 6")
