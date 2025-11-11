"""Initial schema for tuina booking backend.

Revision ID: c38e722ebf4e
Revises:
Create Date: 2025-11-07 14:44:08.371434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c38e722ebf4e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = sa.Enum("customer", "technician", "admin", name="userrole")
appointment_status = sa.Enum("scheduled", "completed", "no_show", name="appointmentstatus")


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("location_id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=255)),
        sa.Column("city", sa.String(length=120)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=26), primary_key=True),
        sa.Column("wechat_openid", sa.String(length=64), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="customer"),
        sa.Column("display_name", sa.String(length=100)),
        sa.Column("phone_number", sa.String(length=32)),
        sa.Column("default_location_id", sa.String(length=26), sa.ForeignKey("locations.location_id", ondelete="SET NULL")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_wechat_openid", "users", ["wechat_openid"], unique=True)
    op.create_index("ix_users_default_location_id", "users", ["default_location_id"])

    op.create_table(
        "services",
        sa.Column("service_id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.String(length=255)),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("concurrency_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "patients",
        sa.Column("patient_id", sa.String(length=26), primary_key=True),
        sa.Column("managed_by_user_id", sa.String(length=26), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone_number", sa.String(length=32)),
        sa.Column("birth_date", sa.String(length=20)),
        sa.Column("notes", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("managed_by_user_id", "full_name", name="uq_patient_name_per_user"),
    )

    op.create_table(
        "technicians",
        sa.Column("technician_id", sa.String(length=26), primary_key=True),
        sa.Column("user_id", sa.String(length=26), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("bio", sa.String(length=255)),
        sa.Column("avatar_url", sa.String(length=255)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("restricted_by_quota", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "offerings",
        sa.Column("offering_id", sa.String(length=26), primary_key=True),
        sa.Column("technician_id", sa.String(length=26), sa.ForeignKey("technicians.technician_id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", sa.String(length=26), sa.ForeignKey("services.service_id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.String(length=26), sa.ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("technician_id", "service_id", "location_id", name="uq_offering_combo"),
        sa.CheckConstraint("price >= 0", name="ck_offering_price_positive"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_offering_duration_positive"),
    )

    op.create_table(
        "business_hours",
        sa.Column("rule_id", sa.String(length=26), primary_key=True),
        sa.Column("technician_id", sa.String(length=26), sa.ForeignKey("technicians.technician_id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.String(length=26), sa.ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(timezone=True), nullable=False),
        sa.Column("end_time", sa.Time(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("technician_id", "location_id", "day_of_week", "start_time", name="uq_business_hour_slot"),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_business_hours_dow"),
    )

    op.create_table(
        "schedule_exceptions",
        sa.Column("exception_id", sa.String(length=26), primary_key=True),
        sa.Column("technician_id", sa.String(length=26), sa.ForeignKey("technicians.technician_id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.String(length=26), sa.ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("start_time", sa.Time(timezone=True)),
        sa.Column("end_time", sa.Time(timezone=True)),
        sa.Column("reason", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("technician_id", "location_id", "date", name="uq_schedule_exception"),
    )

    op.create_table(
        "appointments",
        sa.Column("appointment_id", sa.String(length=26), primary_key=True),
        sa.Column("patient_id", sa.String(length=26), sa.ForeignKey("patients.patient_id", ondelete="CASCADE"), nullable=False),
        sa.Column("booked_by_user_id", sa.String(length=26), sa.ForeignKey("users.user_id", ondelete="SET NULL")),
        sa.Column("offering_id", sa.String(length=26), sa.ForeignKey("offerings.offering_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("technician_id", sa.String(length=26), sa.ForeignKey("technicians.technician_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", appointment_status, nullable=False, server_default="scheduled"),
        sa.Column("booked_by_role", user_role, nullable=False),
        sa.Column("price_at_booking", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_time > start_time", name="ck_appointments_time_order"),
    )
    op.create_index("ix_appointments_technician_start", "appointments", ["technician_id", "start_time"])


def downgrade() -> None:
    op.drop_index("ix_appointments_technician_start", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("schedule_exceptions")
    op.drop_table("business_hours")
    op.drop_table("offerings")
    op.drop_table("technicians")
    op.drop_table("patients")
    op.drop_table("services")
    op.drop_index("ix_users_default_location_id", table_name="users")
    op.drop_table("users")
    op.drop_table("locations")
    appointment_status.drop(op.get_bind(), checkfirst=False)
    user_role.drop(op.get_bind(), checkfirst=False)
