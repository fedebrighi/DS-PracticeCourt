from fastapi import FastAPI
from contextlib import asynccontextmanager
from shared.config import get_settings
from shared.db import db_manager
from shared.redis_client import redis_manager
from fastapi.middleware.cors import CORSMiddleware
from shared.schemas import HealthResponse

# STESSE COSE CHE HO FATTO IN MAIN.PY DI FIELDNODE, CAMBIA SOLO CHE CE' UTILITY INVECE DI FIELD

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.init()
    redis_manager.init()
    yield
    await db_manager.close()
    await redis_manager.close()

app = FastAPI(title="Utility Node", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service=get_settings().node_id)

@app.get("/utilities")
async def list_utilities():
    return {"message": "stub"}

@app.get("/utilities/{utility_id}")
async def get_utility(utility_id: int):
    return {"message": f"stub utility {utility_id}"}

@app.post("/utility-bookings")
async def create_utility_booking():
    return {"message": "stub"}