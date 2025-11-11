"""Remove schedule exceptions table.

Revision ID: 2e9bf0f7b35c
Revises: 7d3c4a6b9e8f
Create Date: 2025-02-14 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2e9bf0f7b35c"
down_revision: Union[str, Sequence[str], None] = "7d3c4a6b9e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("schedule_exceptions")


def downgrade() -> None:
    op.create_table(
        "schedule_exceptions",
        sa.Column("exception_id", sa.String(length=26), nullable=False),
        sa.Column("technician_id", sa.String(length=26), nullable=False),
        sa.Column("location_id", sa.String(length=26), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.Column("start_time", sa.Time(timezone=True), nullable=True),
        sa.Column("end_time", sa.Time(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["technician_id"], ["technicians.technician_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exception_id"),
        sa.UniqueConstraint("technician_id", "location_id", "date", name="uq_schedule_exception"),
    )
