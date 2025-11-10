"""Replace weekly quota with explicit morning/afternoon limits.

Revision ID: 5f6c0b7b8f2c
Revises: 8af5d3f44c5d
Create Date: 2025-02-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5f6c0b7b8f2c"
down_revision: Union[str, Sequence[str], None] = "8af5d3f44c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("technicians", sa.Column("morning_quota_limit", sa.Integer(), nullable=True))
    op.add_column("technicians", sa.Column("afternoon_quota_limit", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE technicians
        SET
            morning_quota_limit = daily_quota_limit,
            afternoon_quota_limit = daily_quota_limit
        """
    )

    op.drop_column("technicians", "weekly_quota_limit")
    op.drop_column("technicians", "daily_quota_limit")


def downgrade() -> None:
    op.add_column("technicians", sa.Column("daily_quota_limit", sa.Integer(), nullable=True))
    op.add_column("technicians", sa.Column("weekly_quota_limit", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE technicians
        SET
            daily_quota_limit = COALESCE(morning_quota_limit, afternoon_quota_limit),
            weekly_quota_limit = afternoon_quota_limit
        """
    )

    op.drop_column("technicians", "afternoon_quota_limit")
    op.drop_column("technicians", "morning_quota_limit")
