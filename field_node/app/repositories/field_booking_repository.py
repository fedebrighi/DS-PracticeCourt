from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import FieldBooking
from shared.schemas import BookingStatus

# REPOSITORY PER LE OPERAZIONI CRUD SULLA TABELLA FIELDS BOOKING (COME FIELD_REPOSITORY)

async def get_all(db: AsyncSession) -> list[FieldBooking]: # RESTITUISCE TUTTI I CAMPI PRESENTI NEL DB
    result = await db.execute(select(FieldBooking))
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, booking_id: int) -> FieldBooking | None: # RESITUISCE UN CAMPO PER ID
    result = await db.execute(select(FieldBooking).where(FieldBooking.id == booking_id))
    return result.scalar_one_or_none()

async def create( # CREAZIONE DI UN NUOVO CAMPO
        db: AsyncSession,
        field_id: int,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        status: BookingStatus = BookingStatus.PENDING,
) -> FieldBooking:
    booking = FieldBooking(
        field_id = field_id,
        user_id = user_id,
        start_time = start_time,
        end_time = end_time,
        status = status,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking  # RITORNA L OGGETTO AGGIORNATO DAL DB

async def update_status( # AGGIORNA LO STATO DI UNA PRENOTAZIONE ESISTENTE
        db: AsyncSession,
        booking_id: int,
        status: BookingStatus,
) -> FieldBooking | None:
    booking = await get_by_id(db, booking_id)
    if not booking:
        return None
    booking.status = status
    await db.commit()
    await db.refresh(booking)
    return booking
