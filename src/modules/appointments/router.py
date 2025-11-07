"""Appointments API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import require_admin, require_customer
from src.modules.appointments.schemas import (
    AppointmentAdminCreate,
    AppointmentCreate,
    AppointmentPublic,
    AppointmentUpdate,
)
from src.modules.appointments.service import AppointmentService
from src.modules.users.models import User

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])
admin_router = APIRouter(prefix="/api/v1/admin/appointments", tags=["admin-appointments"])


def get_service(db: AsyncSession = Depends(get_db)) -> AppointmentService:
    return AppointmentService(db)


@router.get("/me", response_model=list[AppointmentPublic])
async def my_appointments(
    current_user: User = Depends(require_customer),
    service: AppointmentService = Depends(get_service),
) -> list[AppointmentPublic]:
    return await service.list_for_user(current_user)


@router.post("", response_model=AppointmentPublic, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    current_user: User = Depends(require_customer),
    service: AppointmentService = Depends(get_service),
) -> AppointmentPublic:
    return await service.create_customer(payload, current_user)


@router.post("/{appointment_id}/cancel", response_model=AppointmentPublic)
async def cancel_appointment(
    appointment_id: str,
    current_user: User = Depends(require_customer),
    service: AppointmentService = Depends(get_service),
) -> AppointmentPublic:
    return await service.cancel_for_user(appointment_id, current_user)


@admin_router.get("", response_model=list[AppointmentPublic])
async def admin_list_appointments(
    _: User = Depends(require_admin),
    service: AppointmentService = Depends(get_service),
) -> list[AppointmentPublic]:
    return await service.admin_list()


@admin_router.post("", response_model=AppointmentPublic, status_code=status.HTTP_201_CREATED)
async def admin_create_appointment(
    payload: AppointmentAdminCreate,
    current_user: User = Depends(require_admin),
    service: AppointmentService = Depends(get_service),
) -> AppointmentPublic:
    return await service.admin_create(payload, current_user)


@admin_router.put("/{appointment_id}", response_model=AppointmentPublic)
async def admin_update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    _: User = Depends(require_admin),
    service: AppointmentService = Depends(get_service),
) -> AppointmentPublic:
    return await service.admin_update(appointment_id, payload)


@admin_router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_appointment(
    appointment_id: str,
    _: User = Depends(require_admin),
    service: AppointmentService = Depends(get_service),
) -> None:
    await service.admin_delete(appointment_id)
