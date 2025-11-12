from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from src.core.config import settings
from src.modules.appointments.models import Appointment
from src.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate
from src.modules.appointments.service import AppointmentService
from src.modules.catalog.models import Location, Offering, Service
from src.modules.schedule.models import BusinessHour
from src.modules.schedule.service import (
    UNAVAILABLE_REASON_CONFLICT,
    UNAVAILABLE_REASON_QUOTA,
    AvailabilityRequest,
    get_availability,
)
from src.modules.users.models import Patient, Technician, User
from src.shared.enums import AppointmentStatus, UserRole, Weekday
from src.shared.ulid import generate_ulid

BASE_RULE_DATE = date(2024, 5, 20)


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
        day_of_week=Weekday.from_date(BASE_RULE_DATE).value,
        rule_date=BASE_RULE_DATE,
        start_time_am=time(9, 0),
        end_time_am=time(12, 0),
        start_time_pm=None,
        end_time_pm=None,
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
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, appointment])
    await db_session.commit()

    request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert len(slots) == 3
    assert slots[0].start.hour == 9 and slots[0].reason == UNAVAILABLE_REASON_CONFLICT
    assert slots[1].reason is None


@pytest.mark.asyncio
async def test_availability_respects_service_concurrency(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    service.concurrency_level = 2
    user = User(user_id=generate_ulid(), wechat_openid="wx-openid-2", role=UserRole.CUSTOMER, is_active=True)
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
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, appointment])
    await db_session.commit()

    request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert len(slots) == 3
    assert slots[0].start.hour == 9 and all(slot.reason is None for slot in slots)


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
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )

    created = await service_layer.create_customer(payload, user)
    assert created.start_time.hour == 9

    with pytest.raises(HTTPException) as exc:
        await service_layer.create_customer(payload, user)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_list_for_user_includes_related_names(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-names", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(
        patient_id=generate_ulid(),
        managed_by_user_id=user.user_id,
        full_name="Display Target",
    )
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )
    await service_layer.create_customer(payload, user)

    items = await service_layer.list_for_user(user)
    assert len(items) == 1
    record = items[0]
    assert record.patient_name == patient.full_name
    assert record.service_name == service.name
    assert record.technician_name == technician.display_name
    assert record.location_name == location.name


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
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, early_appt])
    await db_session.commit()

    monkeypatch.setattr(settings, "father_customer_morning_quota", 1)
    monkeypatch.setattr(settings, "father_customer_afternoon_quota", 1)

    base_request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    customer_slots = await get_availability(base_request, db_session)
    assert customer_slots
    assert all(slot.reason == UNAVAILABLE_REASON_QUOTA for slot in customer_slots)

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
    assert any(slot.reason is None for slot in admin_slots)
    assert any(slot.reason == UNAVAILABLE_REASON_CONFLICT for slot in admin_slots)


@pytest.mark.asyncio
async def test_custom_quota_limit_enforced_without_global_flag(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    technician.restricted_by_quota = False
    technician.morning_quota_limit = 1
    await db_session.commit()

    user = User(user_id=generate_ulid(), wechat_openid="wx-custom", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Quota Test")
    early_appt = Appointment(
        appointment_id=generate_ulid(),
        patient_id=patient.patient_id,
        booked_by_user_id=user.user_id,
        offering_id=offering.offering_id,
        technician_id=technician.technician_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, early_appt])
    await db_session.commit()

    request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert slots
    assert all(slot.reason == UNAVAILABLE_REASON_QUOTA for slot in slots)


@pytest.mark.asyncio
async def test_afternoon_quota_only_blocks_afternoon(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    technician.afternoon_quota_limit = 1
    await db_session.commit()

    existing_hour = (
        await db_session.execute(
            select(BusinessHour).where(
                BusinessHour.technician_id == technician.technician_id,
                BusinessHour.location_id == location.location_id,
                BusinessHour.rule_date == BASE_RULE_DATE,
            )
        )
    ).scalar_one()
    existing_hour.start_time_pm = time(13, 0)
    existing_hour.end_time_pm = time(17, 0)
    await db_session.commit()

    user = User(user_id=generate_ulid(), wechat_openid="wx-afternoon", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Afternoon Limit")
    afternoon_appt = Appointment(
        appointment_id=generate_ulid(),
        patient_id=patient.patient_id,
        booked_by_user_id=user.user_id,
        offering_id=offering.offering_id,
        technician_id=technician.technician_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 13, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 14, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, afternoon_appt])
    await db_session.commit()

    request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert len(slots) >= 1
    morning_slots = [slot for slot in slots if slot.start.hour < 12]
    afternoon_slots = [slot for slot in slots if slot.start.hour >= 12]
    assert morning_slots and afternoon_slots
    assert all(slot.reason is None for slot in morning_slots)
    assert all(slot.reason == UNAVAILABLE_REASON_QUOTA for slot in afternoon_slots)


@pytest.mark.asyncio
async def test_zero_quota_disables_restriction(monkeypatch, db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    technician.restricted_by_quota = True
    technician.morning_quota_limit = 0
    technician.afternoon_quota_limit = 0
    await db_session.commit()

    user = User(user_id=generate_ulid(), wechat_openid="wx-zero", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Zero Limit")
    appt = Appointment(
        appointment_id=generate_ulid(),
        patient_id=patient.patient_id,
        booked_by_user_id=user.user_id,
        offering_id=offering.offering_id,
        technician_id=technician.technician_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
        end_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
        status=AppointmentStatus.SCHEDULED,
        booked_by_role=UserRole.CUSTOMER,
        price_at_booking=Decimal("128.00"),
    )
    db_session.add_all([user, patient, appt])
    await db_session.commit()

    monkeypatch.setattr(settings, "father_customer_morning_quota", 1)
    monkeypatch.setattr(settings, "father_customer_afternoon_quota", 1)

    request = AvailabilityRequest(
        target_date=BASE_RULE_DATE,
        technician_id=technician.technician_id,
        service_id=service.service_id,
        location_id=location.location_id,
        requester_role=UserRole.CUSTOMER,
    )
    slots = await get_availability(request, db_session)
    assert len(slots) >= 1
    assert any(slot.reason is None for slot in slots)


@pytest.mark.asyncio
async def test_customer_can_delete_future_appointment(monkeypatch, db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-delete", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Delete Me")
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )
    created = await service_layer.create_customer(payload, user)

    monkeypatch.setattr(
        AppointmentService,
        "_now",
        lambda self: datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 8, 0, tzinfo=tz),
    )
    await service_layer.delete_for_user(created.appointment_id, user)

    result = await db_session.execute(select(Appointment).where(Appointment.appointment_id == created.appointment_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_booking_updates_user_default_location(db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-pref", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Pref Test")
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )
    await service_layer.create_customer(payload, user)
    await db_session.refresh(user)
    assert user.default_location_id == location.location_id


@pytest.mark.asyncio
async def test_customer_cannot_delete_after_start(monkeypatch, db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-late", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Late Delete")
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )
    created = await service_layer.create_customer(payload, user)

    monkeypatch.setattr(
        AppointmentService,
        "_now",
        lambda self: datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
    )
    with pytest.raises(HTTPException) as exc:
        await service_layer.delete_for_user(created.appointment_id, user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_can_mark_status_after_start(monkeypatch, db_session):
    tz = ZoneInfo("Asia/Shanghai")
    technician, location, service, offering = await _seed_common_catalog(db_session)
    user = User(user_id=generate_ulid(), wechat_openid="wx-done", role=UserRole.CUSTOMER, is_active=True)
    patient = Patient(patient_id=generate_ulid(), managed_by_user_id=user.user_id, full_name="Finish Test")
    db_session.add_all([user, patient])
    await db_session.commit()

    service_layer = AppointmentService(db_session)
    payload = AppointmentCreate(
        offering_id=offering.offering_id,
        patient_id=patient.patient_id,
        start_time=datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 9, 0, tzinfo=tz),
    )
    created = await service_layer.create_customer(payload, user)

    monkeypatch.setattr(
        AppointmentService,
        "_now",
        lambda self: datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 8, 30, tzinfo=tz),
    )
    with pytest.raises(HTTPException):
        await service_layer.admin_update(
            created.appointment_id,
            AppointmentUpdate(status=AppointmentStatus.COMPLETED),
        )

    monkeypatch.setattr(
        AppointmentService,
        "_now",
        lambda self: datetime(BASE_RULE_DATE.year, BASE_RULE_DATE.month, BASE_RULE_DATE.day, 10, 0, tzinfo=tz),
    )
    updated = await service_layer.admin_update(
        created.appointment_id,
        AppointmentUpdate(status=AppointmentStatus.NO_SHOW),
    )
    assert updated.status == AppointmentStatus.NO_SHOW
