"""Add per-technician quota limits.

Revision ID: 8af5d3f44c5d
Revises: c38e722ebf4e
Create Date: 2025-02-09 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8af5d3f44c5d"
down_revision: Union[str, Sequence[str], None] = "c38e722ebf4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("technicians", sa.Column("daily_quota_limit", sa.Integer(), nullable=True))
    op.add_column("technicians", sa.Column("weekly_quota_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("technicians", "weekly_quota_limit")
    op.drop_column("technicians", "daily_quota_limit")
