"""Schedule routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_optional_user
from src.modules.schedule.schemas import AvailabilitySlot
from src.modules.schedule.service import AvailabilityRequest, get_availability
from src.modules.users.models import User
from src.shared.enums import UserRole

router = APIRouter(prefix="/api/v1/schedule", tags=["schedule"])


@router.get("/availability", response_model=list[AvailabilitySlot])
async def availability(
    date_value: date = Query(..., alias="date"),
    technician_id: str = Query(...),
    service_id: str = Query(...),
    location_id: str = Query(...),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> list[AvailabilitySlot]:
    role = current_user.role if current_user else UserRole.CUSTOMER
    request = AvailabilityRequest(
        target_date=date_value,
        technician_id=technician_id,
        service_id=service_id,
        location_id=location_id,
        requester_role=role,
    )
    return await get_availability(request, db)
