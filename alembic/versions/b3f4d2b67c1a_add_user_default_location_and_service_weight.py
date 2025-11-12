"""Add user default location reference and service weight."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b3f4d2b67c1a"
down_revision: Union[str, Sequence[str], None] = "a3dbf6a5d4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    #op.add_column("users", sa.Column("default_location_id", sa.String(length=26), nullable=True))
    #op.create_index("ix_users_default_location_id", "users", ["default_location_id"])
    #op.create_foreign_key(
    #    "fk_users_default_location",
    #    "users",
    #    "locations",
    #    ["default_location_id"],
    #    ["location_id"],
    #    ondelete="SET NULL",
    #)

    op.add_column("services", sa.Column("weight", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE services SET weight = 0 WHERE weight IS NULL")
    op.alter_column("services", "weight", server_default=None)


def downgrade() -> None:
    op.drop_column("services", "weight")

    #op.drop_constraint("fk_users_default_location", "users", type_="foreignkey")
    #op.drop_index("ix_users_default_location_id", table_name="users")
    #op.drop_column("users", "default_location_id")
