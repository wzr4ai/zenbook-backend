"""Catalog schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LocationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    location_id: str = Field(serialization_alias="id")
    name: str
    address: str | None = None
    city: str | None = None
    is_active: bool


class LocationCreate(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    is_active: bool = True


class LocationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    is_active: bool | None = None


class ServicePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_id: str = Field(serialization_alias="id")
    name: str
    description: str | None = None
    default_duration_minutes: int
    concurrency_level: int
    is_active: bool


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    default_duration_minutes: int = 60
    concurrency_level: int = 1
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_duration_minutes: int | None = Field(None, gt=0)
    concurrency_level: int | None = Field(None, gt=0)
    is_active: bool | None = None


class TechnicianPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technician_id: str = Field(serialization_alias="id")
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    is_active: bool
    restricted_by_quota: bool


class TechnicianCreate(BaseModel):
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    user_id: str | None = None
    is_active: bool = True
    restricted_by_quota: bool = False


class TechnicianUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    user_id: str | None = None
    is_active: bool | None = None
    restricted_by_quota: bool | None = None


class OfferingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offering_id: str = Field(serialization_alias="id")
    technician_id: str
    service_id: str
    location_id: str
    price: Decimal
    duration_minutes: int
    is_available: bool
    updated_at: datetime


class OfferingCreate(BaseModel):
    technician_id: str
    service_id: str
    location_id: str
    price: Decimal
    duration_minutes: int = Field(..., gt=0)
    is_available: bool = True


class OfferingUpdate(BaseModel):
    price: Decimal | None = None
    duration_minutes: int | None = Field(None, gt=0)
    is_available: bool | None = None
