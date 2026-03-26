from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pygments.lexers import data


# ENUMS

class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class _ORMBase(BaseModel): # ABILITA CONVERSIONE DIRETTA DA OGGETTI SQLALCHEMY A PYDANTIC
    model_config = ConfigDict(from_attributes=True)

# FIELD

class FieldBase(BaseModel): # CAMPI INVIATI DAL CLIENT QUANDO CREA/AGGIORNA UN CAMPO SPORTIVO
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=255)
    sport_type: str = Field(..., min_length=1, max_length=50)
    price_per_hour: float = 0.0

class FieldResponse(_ORMBase, FieldBase): # AGGIUNGE I CAMPI GENERATI DAL SERVER ALLA RISPOSTA
    model_config = ConfigDict(from_attributes=True) # MODIFICA NECESSARIA PER FAR SI CHE PYDANTIC LEGGA CORRETTAMENTE GLI ATTRIBUTI DELL OGGETTO ORM
    id: int
    is_active: bool
    created_at: datetime

    @field_validator("price_per_hour", mode="before")
    @classmethod
    def decimal_to_float(cls, v):
        return float(v)

# UTILITY

class UtilityBase(BaseModel): # CAMPI INVIATI DAL CLIENT QUANDO CREA/AGGIORNA UN SERVIZIO
    name: str = Field(..., min_length=1, max_length=100)
    description:Optional[str] = Field(default=None, max_length=500)
    price_per_hour: float = 0.0
    utility_type: float

class UtilityResponse(_ORMBase, UtilityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool

    @field_validator("price_per_hour", mode="before")
    @classmethod
    def decimal_to_float(cls, v):
        return float(v)

# FIELD BOOKING

class FieldBookingRequest(BaseModel):
    field_id: int = Field(..., gt=0)
    user_id: str = Field(..., gt=0)
    start_time: datetime
    end_time: datetime
    utility_ids: list[int] = Field(default_factory=list)  # QUALI NODI COINVOLGEREMO NEL 2PC

    @field_validator("end_time")  # VALIDATORE AUTOMATICO PER AVERE END_TIME SUCCESSIVO A START_TIME
    @classmethod
    def end_must_be_after_start(cls, end: datetime, info) -> datetime:
        start = info.data.get("start_time")
        if start and end <= start:
            raise ValueError("end_time must be after start_time")
        return end

class FieldBookingResponse(_ORMBase):  # QUELLO CHE IL SERVER RESTITUISCE INVECE AL CLIENT
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime

# UTILITY BOOKING

class UtilityBookingResponse(_ORMBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    utility_id: int
    booking_id: int
    status: BookingStatus

# GENERIC RESPONSES (USATE DA TUTTI GLI ENDPOINTS)

class HealthResponse(BaseModel):
    status: str
    service: str

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None