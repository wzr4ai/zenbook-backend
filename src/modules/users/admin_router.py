"""Admin-facing routes for user and patient management."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import require_admin
from src.modules.users.models import Patient, User
from src.modules.users.schemas import PatientPublic, UserPublic

router = APIRouter(prefix="/api/v1/admin", tags=["admin-users"])


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.get("/patients", response_model=list[PatientPublic])
async def list_patients(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[Patient]:
    result = await db.execute(select(Patient).order_by(Patient.created_at.desc()))
    return list(result.scalars().all())
