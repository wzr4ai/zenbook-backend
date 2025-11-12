"""Catalog read-only routes for MVP."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.catalog.models import Location, Offering, Service
from src.modules.catalog.schemas import LocationPublic, OfferingPublic, ServicePublic, TechnicianPublic
from src.modules.users.models import Technician

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/locations", response_model=list[LocationPublic])
async def list_locations(db: AsyncSession = Depends(get_db)) -> list[Location]:
    result = await db.execute(select(Location).where(Location.is_active.is_(True)).order_by(Location.name))
    return list(result.scalars().all())


@router.get("/services", response_model=list[ServicePublic])
async def list_services(db: AsyncSession = Depends(get_db)) -> list[Service]:
    result = await db.execute(
        select(Service).where(Service.is_active.is_(True)).order_by(Service.weight.desc(), Service.name)
    )
    return list(result.scalars().all())


@router.get("/technicians", response_model=list[TechnicianPublic])
async def list_technicians(db: AsyncSession = Depends(get_db)) -> list[Technician]:
    result = await db.execute(
        select(Technician)
        .where(Technician.is_active.is_(True))
        .order_by(Technician.weight.desc(), Technician.display_name)
    )
    return list(result.scalars().all())


@router.get("/offerings", response_model=list[OfferingPublic])
async def list_offerings(
    technician_id: str | None = Query(default=None),
    service_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[Offering]:
    stmt = select(Offering).where(Offering.is_available.is_(True))
    if technician_id:
        stmt = stmt.where(Offering.technician_id == technician_id)
    if service_id:
        stmt = stmt.where(Offering.service_id == service_id)
    if location_id:
        stmt = stmt.where(Offering.location_id == location_id)
    stmt = stmt.order_by(Offering.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
