from fastapi import FastAPI
from contextlib import asynccontextmanager
from shared.config import get_settings
from shared.db import db_manager
from shared.redis_client import redis_manager
from fastapi.middleware.cors import CORSMiddleware
from shared.schemas import HealthResponse

@asynccontextmanager  # GESTIONE DI AVVIO E SPEGNIMENTO RISORSE PER LE RICHIESTE
async def lifespan(app: FastAPI):
    db_manager.init()
    redis_manager.init()
    yield
    await db_manager.close()
    await redis_manager.close()

app = FastAPI(title="Field Node", version="0.1.0", lifespan=lifespan)

@app.get("/health", response_model=HealthResponse) # CONTROLLO DELLO STATO DEL NODO
async def health():
    return HealthResponse(status="ok", service=get_settings().node_id)

@app.get("/fields")
async def list_fields():
    return {"message": "test"}

@app.get("/fields/{field_id}")
async def get_field(field_id: int):
    return {"message": f" test field {field_id}"}

@app.post("/bookings")
async def create_booking():
    return {"message": "test"}

@app.get("/bookings/{booking_id}")
async def get_booking(booking_id: int):
    return {"message": f"test booking {booking_id}"}