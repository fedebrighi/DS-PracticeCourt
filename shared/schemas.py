from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ENUMS

class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class _ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# FIELD

class FieldBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=255)
    sport_type: str = Field(..., min_length=1, max_length=50)
    price_per_hour: float = Field(..., gt=0)

class FieldResponse(_ORMBase, FieldBase):
    id: int
    is_available: bool

# UTILITY

class UtilityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description:Optional[str] = Field(default=None, max_length=500)
    price: float = Field(..., gt=0)

class UtilityResponse(_ORMBase, UtilityBase):
    id: int
    is_available: bool

# FIELD BOOKING

class FieldBookingRequest(BaseModel):
    field_id: int = Field(..., gt=0)
    user_id: int = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    utility_ids: list[int] = Field(default_factory=list)

    @field_validator("end_time")
    @classmethod
    def end_must_be_after_start(cls, end: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and end <= start:
            raise ValueError("end_time must be after start_time")
        return end

class FieldBookingResponse(_ORMBase):
    id: int
    field_int: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    transaction_id: str

# UTILITY BOOKING

class UtilityBookingResponse(_ORMBase):
    id: int
    utility_id: int
    field_booking_id: int
    statistics: BookingStatus

# GENERIC RESPONSES

class HealthResponse(BaseModel):
    status: str
    service: str

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None