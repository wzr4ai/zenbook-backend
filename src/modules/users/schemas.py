"""Pydantic schemas for users and patients."""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.shared.enums import UserRole


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(serialization_alias="id")
    role: UserRole
    display_name: str | None = None
    phone_number: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class PatientBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(
        validation_alias=AliasChoices("name", "full_name"),
        serialization_alias="name",
    )
    phone_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("phone", "phone_number"),
        serialization_alias="phone",
    )
    birth_date: str | None = None
    notes: str | None = Field(
        default=None,
        validation_alias=AliasChoices("relation", "notes"),
        serialization_alias="relation",
    )


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("name", "full_name"),
        serialization_alias="name",
    )
    phone_number: str | None = Field(
        default=None,
        validation_alias=AliasChoices("phone", "phone_number"),
        serialization_alias="phone",
    )
    birth_date: str | None = None
    notes: str | None = Field(
        default=None,
        validation_alias=AliasChoices("relation", "notes"),
        serialization_alias="relation",
    )


class PatientPublic(PatientBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    patient_id: str = Field(serialization_alias="id")
    managed_by_user_id: str
    created_at: datetime
    updated_at: datetime
