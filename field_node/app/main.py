from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import field_repository, field_booking_repository
from shared.config import get_settings
from shared.db import db_manager, get_db
from shared.redis_client import redis_manager
from shared.schemas import HealthResponse, FieldResponse, FieldBase, FieldBookingResponse, FieldBookingRequest

settings = get_settings()

@asynccontextmanager  # GESTIONE DI AVVIO E SPEGNIMENTO RISORSE PER LE RICHIESTE
async def lifespan(app: FastAPI):
    db_manager.init()
    redis_manager.init()
    yield
    await db_manager.close()
    await redis_manager.close()

app = FastAPI(title="Field Node", vintersion="0.1.0", lifespan=lifespan)

@app.get("/health", response_model= HealthResponse) # CONTROLLO DELLO STATO DEL NODO
async def health():
    return HealthResponse(status="ok", service = get_settings().node_id)

@app.get("/fields", response_model= list[FieldResponse]) # RESITUISCE TUTTI I CAMPI DISPONIBILI
async def list_fields(db: AsyncSession = Depends(get_db)):
    return await field_repository.get_all(db)

@app.get("/fields/{field_id}", response_model= FieldResponse) # RESITUISCE UN CAMPO PER ID
async def get_field(field_id: int, db: AsyncSession = Depends(get_db)):
    field = await field_repository.get_by_id(db, field_id)
    if not field:
        raise HTTPException(status_code=404, detail= "Field not found!")
    return field

@app.post("/fields", response_model= FieldResponse, status_code= 201) # CREA UN NUOVO CAMPO, 201 = CREAZIONE
async def create_field(data: FieldBase, db: AsyncSession = Depends(get_db)):
    return await field_repository.create(
        db,
        name = data.name,
        location = data.location,
        sport_type = data.sport_type,
        price_per_hour = data.price_per_hour,
    )

@app.get("/bookings", response_model= list[FieldBookingResponse]) # RESTITUISCE TUTTE LE PRENOTAZIONI
async def list_bookings(db: AsyncSession = Depends(get_db)):
    return await field_booking_repository.get_all(db)

@app.get("/bookings/{booking_id}",response_model= FieldBookingResponse) # RESTITUISCE UNA PRENOTAZIONE PER ID
async def get_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    booking = await field_booking_repository.get_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail= "Booking not found!")
    return booking

@app.post("/bookings", response_model= FieldBookingResponse, status_code= 201) # CREA UNA PRENOTAZIONE
async def create_booking(data: FieldBookingRequest, db: AsyncSession = Depends(get_db)):
    field = await field_repository.get_by_id(db, data.field_id)
    if not field: # CONTROLLO DISPONIBILITA' CAMPO PRE PRENOTAZIONE
        raise HTTPException(status_code=404, detail= "Field not found!")
    if not field.is_active:
        raise HTTPException(status_code=409, detail= "Field not available!") # 409 = CONFLITTO

    booking = await field_booking_repository.create(
        db,
        field_id = data.field_id,
        user_id = data.user_id,
        start_time = data.start_time,
        end_time = data.end_time
    )
    return booking