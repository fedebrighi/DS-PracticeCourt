from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import UtilityBooking
from shared.schemas import BookingStatus


# COME FATTO PER FIELD_BOOKING_REPOSITORY
async def get_all(db: AsyncSession) -> list[UtilityBooking]:
    result = await db.execute(select(UtilityBooking))
    return list(result.scalars().all())

    # QUA USO L'ID SPECIFICO DELLA PRENOTAZIONE DEL CAMPO A CUI VOGLIO ASSOCIARE LE UTILITIES
async def get_by_field_booking(db: AsyncSession, field_booking_id: int) -> list[UtilityBooking]:
    result = await db.execute(select(UtilityBooking).where(
        UtilityBooking.booking_id == field_booking_id)
    )
    return list(result.scalars().all())

async def create(
        db: AsyncSession,
        utility_id: int,
        booking_id: int,
) -> UtilityBooking:
    booking = UtilityBooking(
        utility_id = utility_id,
        booking_id = booking_id,
        status = BookingStatus.PENDING # LA NUOVA PRENOTAZIONE UTILITY PARTE IN PENDING
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking

async def update_status(  # AGGIORNO LO STATO DELLA PRENOTAZIONE UTILITY
        db: AsyncSession,
        booking_id: int,
        status: BookingStatus,
) -> UtilityBooking | None:
    result = await db.execute(
        select(UtilityBooking).where(UtilityBooking.id == booking_id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        return None
    booking.status = status
    await db.commit()
    await db.refresh(booking)
    return booking