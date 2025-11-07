"""Catalog read-only routes for MVP."""

from fastapi import APIRouter, Depends
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
    result = await db.execute(select(Service).where(Service.is_active.is_(True)).order_by(Service.name))
    return list(result.scalars().all())


@router.get("/technicians", response_model=list[TechnicianPublic])
async def list_technicians(db: AsyncSession = Depends(get_db)) -> list[Technician]:
    result = await db.execute(select(Technician).where(Technician.is_active.is_(True)).order_by(Technician.display_name))
    return list(result.scalars().all())


@router.get("/offerings", response_model=list[OfferingPublic])
async def list_offerings(db: AsyncSession = Depends(get_db)) -> list[Offering]:
    result = await db.execute(
        select(Offering).where(Offering.is_available.is_(True)).order_by(Offering.updated_at.desc())
    )
    return list(result.scalars().all())
