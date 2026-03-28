from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import and_
from shared.locks import DistributedLock
from shared.models import FieldBooking
from shared.schemas import BookingStatus
from redis.asyncio import Redis

_LOCK_TTL_MS = 5_000  # 5 SECONDI PER LA SEZIONE CRITICA

# REPOSITORY PER LE OPERAZIONI CRUD SULLA TABELLA FIELDS BOOKING (COME FIELD_REPOSITORY)

async def get_all(db: AsyncSession) -> list[FieldBooking]: # RESTITUISCE TUTTI I CAMPI PRESENTI NEL DB
    result = await db.execute(select(FieldBooking))
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, booking_id: int) -> FieldBooking | None: # RESITUISCE UN CAMPO PER ID
    result = await db.execute(select(FieldBooking).where(FieldBooking.id == booking_id))
    return result.scalar_one_or_none()

# VERIFICA CHE NON ESISTA GIA UNA PRENOTAZIONE SOVRAPPOSTA PER QUEL CAMPO
async def check_availability(
        db: AsyncSession,
        field_id: int,
        start_time: datetime,
        end_time: datetime,
) -> bool:
    result = await db.execute(
        select(FieldBooking).where(
            and_(
                FieldBooking.field_id == field_id, # CONSIDERO SOLO PRENOTAZIONI PENDING O CONFIRMED
                FieldBooking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                FieldBooking.start_time < end_time,
                FieldBooking.end_time > start_time,
            )
        )
    )
    return result.scalar_one_or_none() is None

async def create( # CREAZIONE DI UNA NUOVA PRENOTAZIONE
        db: AsyncSession,
        redis: Redis,
        field_id: int,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
) -> FieldBooking | None:
    lock = DistributedLock(redis)
    lock_key = f"field:{field_id}"
    token = await lock.acquire(lock_key, _LOCK_TTL_MS) # ACQUISISCO IL LOCK
    if token is None:
        return None
    try:
        available = await check_availability(db, field_id, start_time, end_time) # VERIFICO DISPONIBILITA
        if not available:
            return None
        # INSERISCO
        booking = FieldBooking(
            field_id = field_id,
            user_id = user_id,
            start_time = start_time,
            end_time = end_time,
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking  # RITORNA L OGGETTO AGGIORNATO DAL DB
    finally:
        await lock.release(lock_key, token) # RILASCIO IL LOCK

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
