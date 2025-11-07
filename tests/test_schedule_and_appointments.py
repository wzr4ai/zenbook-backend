from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from src.core.config import settings
from src.modules.appointments.models import Appointment
from src.modules.appointments.schemas import AppointmentCreate
from src.modules.appointments.service import AppointmentService
from src.modules.catalog.models import Location, Offering, Service
from src.modules.schedule.models import BusinessHour
from src.modules.schedule.service import AvailabilityRequest, get_availability
from src.modules.users.models import Patient, Technician, User
from src.shared.enums import AppointmentStatus, UserRole
from src.shared.ulid import generate_ulid


async def _seed_common_catalog(db_session):
    technician = Technician(technician_id=generate_ulid(), display_name="Master Li", restricted_by_quota=False, is_active=True)
    location = Location(location_id=generate_ulid(), name="Main Hall", is_active=True)
    service = Service(
        service_id=generate_ulid(),
        name="TuiNa",
        default_duration_minutes=60,
        concurrency_level=1,
        is_active=True,
    )
    offering = Offering(
        offering_id=generate_ulid(),
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        price=Decimal("128.00"),
        duration_minutes=60,
        is_available=True,
    )
    business_hour = BusinessHour(
        rule_id=generate_ulid(),
        technician_id=technician.technician_id,
        location_id=location.location_id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add_all([technician, location, service, offering, business_hour])
    await db_session.commit()
    return technician, location, service, offering


@pytest.mark.asyncio
async def test_availability_excludes_conflicting_appointments(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-openid", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(
        patient_id=generate_ulid(),
        managed_by_user_id=user.user_id,
        full_name="Test Patient",
    )
    appointment = Appointment(
        appointment_id=generate_ulid(),
        patient_id=patient.patient_id,
        booked_by_user_id=user.user_id,
        offering_id=offering.offering_id,
        technician_id=technician.technician_id,
        start_time=datetime(2024, 5, 20, 9, 0, tzinfo=tz),
        end_time=datetime(2024, 5, 20, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, appointment])
    await db_session.commit()

    request = AvailabilityRequest(
        target_date=date(2024, 5, 20),
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert len(slots) == 2
    assert slots[0].start.hour == 10 and slots[0].end.hour == 11


@pytest.mark.asyncio
async def test_customer_booking_requires_free_slot(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-user", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(
        patient_id=generate_ulid(),
        managed_by_user_id=user.user_id,
        full_name="Customer",
    )
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(2024, 5, 20, 9, 0, tzinfo=tz),
    )

    created = await service_layer.create_customer(payload, user)
    assert created.start_time.hour == 9

    with pytest.raises(HTTPException) as exc:
        await service_layer.create_customer(payload, user)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_father_quota_blocks_customer_but_not_admin(monkeypatch, db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    technician.restricted_by_quota = True
    await db_session.commit()
    user = User(user_id=generate_ulid(), wechat_openid="wx-father", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(
        patient_id=generate_ulid(),
        managed_by_user_id=user.user_id,
        full_name="Quota Customer",
    )
    early_appt = Appointment(
        appointment_id=generate_ulid(),
        patient_id=patient.patient_id,
        booked_by_user_id=user.user_id,
        offering_id=offering.offering_id,
        technician_id=technician.technician_id,
        start_time=datetime(2024, 5, 20, 9, 0, tzinfo=tz),
        end_time=datetime(2024, 5, 20, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, early_appt])
    await db_session.commit()

    monkeypatch.setattr(settings, "father_customer_daily_quota", 1)
    monkeypatch.setattr(settings, "father_customer_weekly_quota", 1)

    base_request = AvailabilityRequest(
        target_date=date(2024, 5, 20),
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    customer_slots = await get_availability(base_request, db_session)
    assert customer_slots == []

    admin_slots = await get_availability(
        AvailabilityRequest(
            target_date=base_request.target_date,
            technician_id=base_request.technician_id,
            service_id=base_request.service_id,
            location_id=base_request.location_id,
            requester_role=UserRole.ADMIN,
        ),
        db_session,
    )
    assert len(admin_slots) >= 1
