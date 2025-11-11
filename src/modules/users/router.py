"""User and patient routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_user, require_customer
from src.modules.users.models import Patient, User
from src.modules.users.schemas import PatientCreate, PatientPublic, PatientUpdate, UserPublic, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    update_data = payload.model_dump(exclude_unset=True)
    if "display_name" in update_data:
        value = update_data["display_name"]
        if value is not None:
            cleaned = value.strip()
            if not cleaned:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="display_name cannot be empty")
            update_data["display_name"] = cleaned
        setattr(current_user, "display_name", update_data["display_name"])
    if not update_data:
        return current_user
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/patients", response_model=list[PatientPublic])
async def list_patients(
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> list[Patient]:
    result = await db.execute(
        select(Patient).where(Patient.managed_by_user_id == current_user.user_id).order_by(Patient.created_at)
    )
    return list(result.scalars().all())


@router.post("/patients", response_model=PatientPublic, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    patient = Patient(managed_by_user_id=current_user.user_id, **payload.model_dump())
    db.add(patient)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient with same name exists")
    await db.refresh(patient)
    return patient


async def _get_patient_for_user(patient_id: str, user: User, db: AsyncSession) -> Patient:
    result = await db.execute(
        select(Patient).where(
            Patient.patient_id == patient_id,
            Patient.managed_by_user_id == user.user_id,
        )
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.put("/patients/{patient_id}", response_model=PatientPublic)
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    patient = await _get_patient_for_user(patient_id, current_user, db)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(patient, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient with same name exists")
    await db.refresh(patient)
    return patient


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: str,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> None:
    patient = await _get_patient_for_user(patient_id, current_user, db)
    await db.delete(patient)
    await db.commit()
