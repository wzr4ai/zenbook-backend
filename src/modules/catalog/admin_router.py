"""Admin catalog CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import require_admin
from src.modules.catalog.models import Location, Offering, Service
from src.modules.catalog.schemas import (
    LocationCreate,
    LocationPublic,
    LocationUpdate,
    OfferingCreate,
    OfferingPublic,
    OfferingUpdate,
    ServiceCreate,
    ServicePublic,
    ServiceUpdate,
    TechnicianCreate,
    TechnicianPublic,
    TechnicianUpdate,
)
from src.modules.users.models import Technician, User

router = APIRouter(prefix="/api/v1/admin/catalog", tags=["admin-catalog"])


async def _get_entity(db: AsyncSession, model, column, value, not_found: str):
    stmt = select(model).where(column == value)
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
    return entity


@router.post("/locations", response_model=LocationPublic, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LocationPublic:
    location = Location(**payload.model_dump())
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


@router.get("/locations", response_model=list[LocationPublic])
async def list_locations(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[LocationPublic]:
    result = await db.execute(select(Location).order_by(Location.created_at))
    return list(result.scalars().all())


@router.put("/locations/{location_id}", response_model=LocationPublic)
async def update_location(
    location_id: str,
    payload: LocationUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LocationPublic:
    location = await _get_entity(db, Location, Location.location_id, location_id, "Location not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, field, value)
    await db.commit()
    await db.refresh(location)
    return location


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    location = await _get_entity(db, Location, Location.location_id, location_id, "Location not found")
    await db.delete(location)
    await db.commit()


@router.post("/services", response_model=ServicePublic, status_code=status.HTTP_201_CREATED)
async def create_service(
    payload: ServiceCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ServicePublic:
    service = Service(**payload.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@router.get("/services", response_model=list[ServicePublic])
async def list_services(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ServicePublic]:
    result = await db.execute(select(Service).order_by(Service.created_at))
    return list(result.scalars().all())


@router.put("/services/{service_id}", response_model=ServicePublic)
async def update_service(
    service_id: str,
    payload: ServiceUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ServicePublic:
    service = await _get_entity(db, Service, Service.service_id, service_id, "Service not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = await _get_entity(db, Service, Service.service_id, service_id, "Service not found")
    await db.delete(service)
    await db.commit()


@router.post("/technicians", response_model=TechnicianPublic, status_code=status.HTTP_201_CREATED)
async def create_technician(
    payload: TechnicianCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TechnicianPublic:
    technician = Technician(**payload.model_dump())
    db.add(technician)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.get("/technicians", response_model=list[TechnicianPublic])
async def list_technicians(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TechnicianPublic]:
    result = await db.execute(select(Technician).order_by(Technician.created_at))
    return list(result.scalars().all())


@router.put("/technicians/{technician_id}", response_model=TechnicianPublic)
async def update_technician(
    technician_id: str,
    payload: TechnicianUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TechnicianPublic:
    technician = await _get_entity(db, Technician, Technician.technician_id, technician_id, "Technician not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(technician, field, value)
    await db.commit()
    await db.refresh(technician)
    return technician


@router.delete("/technicians/{technician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technician(
    technician_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    technician = await _get_entity(db, Technician, Technician.technician_id, technician_id, "Technician not found")
    await db.delete(technician)
    await db.commit()


@router.post("/offerings", response_model=OfferingPublic, status_code=status.HTTP_201_CREATED)
async def create_offering(
    payload: OfferingCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingPublic:
    offering = Offering(**payload.model_dump())
    db.add(offering)
    await db.commit()
    await db.refresh(offering)
    return offering


@router.get("/offerings", response_model=list[OfferingPublic])
async def list_offerings(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[OfferingPublic]:
    result = await db.execute(select(Offering).order_by(Offering.updated_at.desc()))
    return list(result.scalars().all())


@router.put("/offerings/{offering_id}", response_model=OfferingPublic)
async def update_offering(
    offering_id: str,
    payload: OfferingUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingPublic:
    offering = await _get_entity(db, Offering, Offering.offering_id, offering_id, "Offering not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(offering, field, value)
    await db.commit()
    await db.refresh(offering)
    return offering


@router.delete("/offerings/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offering(
    offering_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    offering = await _get_entity(db, Offering, Offering.offering_id, offering_id, "Offering not found")
    await db.delete(offering)
    await db.commit()
