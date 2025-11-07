"""Pydantic schemas for users and patients."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.shared.enums import UserRole


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(serialization_alias="id")
    role: UserRole
    display_name: str | None = None
    phone_number: str | None = None


class PatientBase(BaseModel):
    full_name: str
    phone_number: str | None = None
    birth_date: str | None = None
    notes: str | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None
    birth_date: str | None = None
    notes: str | None = None


class PatientPublic(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(serialization_alias="id")
    managed_by_user_id: str
    created_at: datetime
    updated_at: datetime
