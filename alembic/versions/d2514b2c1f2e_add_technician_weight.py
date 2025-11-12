"""Add weight to technicians for auto default ordering.

Revision ID: d2514b2c1f2e
Revises: 5f6c0b7b8f2c
Create Date: 2025-03-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2514b2c1f2e"
down_revision: Union[str, Sequence[str], None] = "b3f4d2b67c1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "technicians",
        sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("technicians", "weight")
