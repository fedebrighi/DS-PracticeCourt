from datetime import datetime
from typing import Optional

from sqlalchemy import (DateTime, Enum, Float, Integer, String)
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.schemas import BookingStatus


class Base(DeclarativeBase):
    """Common Base for all ORM models in the project"""
    pass

# GESTITI DA FIELD NODE

class Field(Base): # MAPPO IN OGGETTI PYTHON LE CLASSI DEL DATABASE GRAZIE ALL ORM DI SQLALCHEMY
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(Integer, primary_key = True, autoincrement = True)
    name: Mapped[str] = mapped_column(String(100), nullable = False)
    location: Mapped[str] = mapped_column(String(200), nullable = False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable = False)
    price_per_hour: Mapped[float] = mapped_column(Float, nullable = False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable = False)

class FieldBooking(Base):
    __tablename__ =  "field_bookings"
    id: Mapped[int] = mapped_column(Integer, primary_key = True, autoincrement = True)
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable = False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable = False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable = False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, values_callable = lambda obj: [e.value for e in obj]), # USA I VALORI STRINGA DELL ENUM PYTHN PER ALLINEARSI A QUELLA NATIVA CHE SI TROVA IN INIT.SQL
        default = BookingStatus.PENDING,
        nullable = False,
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable = True)

# GESTITI DA UTILITY NODE

class Utility(Base):
    __tablename__ = "utilities"
    id: Mapped[int] = mapped_column(Integer, primary_key = True, autoincrement = True)
    name: Mapped[str] = mapped_column(String(100), nullable = False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable = True)
    price: Mapped[float] = mapped_column(Float, nullable = False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable = False)

class UtilityBooking(Base):
    __tablename__ =  "utility_bookings"
    id: Mapped[int] = mapped_column(Integer, primary_key = True, autoincrement = True)
    utility_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilities.id"), nullable = False)
    field_booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("field_bookings.id"), nullable = False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, values_callable = lambda obj: [e.value for e in obj]),
        default = BookingStatus.PENDING,
        nullable = False,
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable = True)