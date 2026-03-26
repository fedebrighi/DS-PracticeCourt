from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Field

# REPOSITORY PER LE OPERAZIONI CRUD SULLA TABELLA FIELDS

async def get_all(db: AsyncSession) -> list[Field]: # RESTITUISCE TUTTI I CAMPI PRESENTI NEL DB
    result = await db.execute(select(Field))
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, field_id: int) -> Field | None: # RESITUISCE UN CAMPO PER ID
    result = await db.execute(select(Field).where(Field.id == field_id))
    return result.scalar_one_or_none()

async def create( # CREAZIONE DI UN NUOVO CAMPO
        db: AsyncSession,
        name: str,
        location: str,
        sport_type: str,
        price_per_hour: float,
        is_active: bool = True,
) -> Field:
    field = Field(
        name = name,
        location = location,
        sport_type = sport_type,
        price_per_hour = price_per_hour,
        is_active = is_active
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field  # RITORNA L OGGETTO AGGIORNATO DAL DB