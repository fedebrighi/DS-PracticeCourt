from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import Utility

#SEGUE LA STESSA LOGICA CHE HO GIA IMPLEMENTATO IN QUELLI DEI FIELDS

async def get_all(db:AsyncSession) -> list[Utility]:
    result = await db.execute(select(Utility))
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, utility_id: int) -> Utility | None:
    result = await db.execute(select(Utility).where(Utility.id == utility_id))
    return result.scalar_one_or_none()

async def create( # CREO UNA NUOVA UITLITY
        db: AsyncSession,
        name: str,
        utility_type: str | None,
        price_per_hour: float,
        is_active: bool = True,
) -> Utility:
    utility = Utility(
        name = name,
        utility_type = utility_type,
        price_per_hour = price_per_hour,
        is_active = is_active,
    )

    db.add(utility)
    await db.commit()
    await db.refresh(utility)
    return utility