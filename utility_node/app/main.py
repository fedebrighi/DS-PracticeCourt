from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from shared.config import get_settings
from shared.db import db_manager, get_db
from shared.redis_client import redis_manager
from shared.schemas import HealthResponse, UtilityResponse, UtilityBookingResponse, UtilityBase, PrepareResponse, \
    TwoPCVote, PrepareRequest, CommitRollbackResponse, CommitRollbackRequest, BookingStatus
from app.repositories import utility_repository, utility_booking_repository
from shared.logging_config import setup_logging

# STESSE COSE CHE HO FATTO IN MAIN.PY DI FIELDNODE, QUESTO È RELATIVO ALLE PRENOTAZIONI

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    db_manager.init()
    redis_manager.init()
    yield
    await db_manager.close()
    await redis_manager.close()

app = FastAPI(title="Utility Node", version="0.1.0", lifespan=lifespan)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service=get_settings().node_id)

@app.get("/utilities", response_model=list[UtilityResponse])
async def list_utilities(db: AsyncSession = Depends(get_db)):
    return await utility_repository.get_all(db)

@app.get("/utilities/{utility_id}", response_model=UtilityResponse) # RESTITUISCE UTILITIES RELATIVE A UNO SPECIFICO ID
async def get_utility(utility_id: int, db: AsyncSession = Depends(get_db)):
    utility = await utility_repository.get_by_id(db, utility_id)
    if not utility:
        raise HTTPException(status_code=404, detail= "Utility not found!")
    return utility

@app.post("/utilities", response_model=UtilityResponse, status_code=201) # CREA UNA NUOVA UTILITY
async def create_utility_booking(data: UtilityBase, db: AsyncSession = Depends(get_db)):
    return await utility_repository.create(
        db,
        name = data.name,
        utility_type = data.utility_type,
        price_per_hour = data.price_per_hour,
    )

@app.get("/utility-bookings", response_model=list[UtilityBookingResponse])
async def list_utility_bookings(db: AsyncSession = Depends(get_db)):
    return await utility_booking_repository.get_all(db)

@app.get("/utility-bookings/by-field-booking/{booking_id}", response_model=list[UtilityBookingResponse]) # RESTITUISCE PRENOTAZIONI DI UTILITIES RELATIVE
async def get_by_field_booking(booking_id: int, db: AsyncSession = Depends(get_db)):                    # ALL ID DELLA PRENOTAZIONE DI UN CAMPO
    return await utility_booking_repository.get_by_field_booking(db, booking_id)

# ENDPOINTS DEL 2PC

# CONTROLLA SE LA UTILITY È DISPONIBILE E PRENOTA IN PENDING VOTANDO YES O NO
@app.post("/internal/prepare", response_model=PrepareResponse)
async def internal_prepare(req: PrepareRequest, db: AsyncSession = Depends(get_db)):
    utility = await utility_repository.get_by_id(db, req.utility_id)
    if not utility or not utility.is_active:
        return PrepareResponse(vote=TwoPCVote.NO, reason=f"Utility {req.utility_id} not found or inactive!",)
    try:
        booking = await utility_booking_repository.create(db, req.utility_id, req.field_booking_id)
        return PrepareResponse(vote=TwoPCVote.YES, utility_booking_id = booking.id)
    except Exception as e:
        return PrepareResponse(vote=TwoPCVote.NO, reason=str(e))

# CONFERMA TUTTE LE UTILITY_BOOKINGS INDICATE AGGIORNANDO DA PENDING A CONFIRMED
@app.post("/internal/commit", response_model=CommitRollbackResponse)
async def internal_commit(req: CommitRollbackRequest, db: AsyncSession = Depends(get_db)):
    for ub_id in req.utility_booking_ids:
        await utility_booking_repository.update_status(db, ub_id, BookingStatus.CONFIRMED)
    return CommitRollbackResponse(ok=True)

# ANNULLA TUTTE LE UTILITY_BOOKINGS INDICATE AGGIORNANDO DA PENDING A CANCELLED
@app.post("/internal/rollback", response_model=CommitRollbackResponse)
async def internal_rollback(req: CommitRollbackRequest, db: AsyncSession = Depends(get_db)):
    for ub_id in req.utility_booking_ids:
        await utility_booking_repository.update_status(db, ub_id, BookingStatus.CANCELLED)
    return CommitRollbackResponse(ok=True)



