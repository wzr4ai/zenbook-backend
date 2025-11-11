"""Switch cancellation flow to deletion and add no_show status."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3dbf6a5d4c7"
down_revision: Union[str, Sequence[str], None] = "2e9bf0f7b35c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_VALUES = ("scheduled", "completed", "no_show")
OLD_VALUES = ("scheduled", "completed", "cancelled")


def _enum(values: tuple[str, ...], name: str = "appointmentstatus") -> sa.Enum:
    return sa.Enum(*values, name=name)


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()

    # Remove historical cancellations so the new enum can drop the value entirely.
    op.execute("DELETE FROM appointments WHERE status = 'cancelled'")

    if _is_postgres(bind):
        op.execute("ALTER TYPE appointmentstatus RENAME TO appointmentstatus_old")
        op.execute("CREATE TYPE appointmentstatus AS ENUM ('scheduled', 'completed', 'no_show')")
        op.execute(
            """
            ALTER TABLE appointments
            ALTER COLUMN status
            TYPE appointmentstatus
            USING status::text::appointmentstatus
            """
        )
        op.execute("DROP TYPE appointmentstatus_old")
    else:
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=_enum(OLD_VALUES),
                type_=_enum(NEW_VALUES),
                existing_nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _is_postgres(bind):
        op.execute("ALTER TYPE appointmentstatus RENAME TO appointmentstatus_new")
        op.execute("CREATE TYPE appointmentstatus AS ENUM ('scheduled', 'completed', 'cancelled')")
        op.execute(
            """
            ALTER TABLE appointments
            ALTER COLUMN status
            TYPE appointmentstatus
            USING (
                CASE
                    WHEN status::text = 'no_show' THEN 'cancelled'
                    ELSE status::text
                END
            )::appointmentstatus
            """
        )
        op.execute("DROP TYPE appointmentstatus_new")
    else:
        op.execute("UPDATE appointments SET status = 'cancelled' WHERE status = 'no_show'")
        with op.batch_alter_table("appointments") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=_enum(NEW_VALUES),
                type_=_enum(OLD_VALUES),
                existing_nullable=False,
            )
