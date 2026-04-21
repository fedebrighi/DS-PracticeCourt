import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pygments.lexers import stata
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.staticfiles import StaticFiles

from shared.events import AVAILABILITY_CHANNEL, publish_booking_event
from shared.config import get_settings
from shared.db import db_manager, get_db
from shared.redis_client import redis_manager, get_redis
from shared.schemas import HealthResponse, FieldResponse, FieldBase, FieldBookingResponse, FieldBookingRequest, BookingStatus
from shared.locks import DistributedLock
from shared.logging_config import setup_logging
from app.two_pc_coordinator import prepare_all, rollback_all, commit_all
from app.repositories import field_repository, field_booking_repository
from app.recovery import recovery_loop, run_recovery

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
_2PC_LOCK_TTL_MS = 30_000

@asynccontextmanager  # GESTIONE DI AVVIO E SPEGNIMENTO RISORSE PER LE RICHIESTE
async def lifespan(app: FastAPI):
    db_manager.init()
    redis_manager.init()
    # AVVIO IL RECOVERY LOOP COME TASK ASYNCIO IN BACKGROUND
    _recovery_task = asyncio.create_task(recovery_loop(settings.utility_node_url))
    logger.info("[RECOVERY] background task started!")
    yield
    # CANCELLATO AUTOMATICAMENTE ALLO SHUTDOWN DEL NODO
    _recovery_task.cancel()
    try:
        await _recovery_task
    except asyncio.CancelledError:
        pass
    await db_manager.close()
    await redis_manager.close()

app = FastAPI(title="Field Node", version="0.1.0", lifespan=lifespan)

# USO LA CARTELLA STATIC COME VOLUME DOCKER
app.mount("/static", StaticFiles(directory="/app/static", html=True), name="static")

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
async def list_bookings(field_id: Optional[int] = None, date: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await field_booking_repository.get_all(db, field_id=field_id, date=date)

@app.get("/bookings/{booking_id}",response_model= FieldBookingResponse) # RESTITUISCE UNA PRENOTAZIONE PER ID
async def get_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    booking = await field_booking_repository.get_by_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail= "Booking not found!")
    return booking

@app.post("/bookings", response_model= FieldBookingResponse, status_code= 201) # CREA UNA PRENOTAZIONE
async def create_booking(data: FieldBookingRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    field = await field_repository.get_by_id(db, data.field_id) # VERIFICO CHE IL CAMPO ESISTA
    if not field: # CONTROLLO DISPONIBILITA' CAMPO PRE-PRENOTAZIONE
        raise HTTPException(status_code=404, detail= "Field not found!")
    if not field.is_active:
        raise HTTPException(status_code=409, detail= "Field not available!") # 409 = CONFLITTO

    booking = await field_booking_repository.create(
        db,
        redis,
        field_id = data.field_id,
        user_id = data.user_id,
        start_time = data.start_time,
        end_time = data.end_time
    )
    if booking is None: # SE LOCK BUSY O SLOT OCCUPATO
        raise HTTPException(status_code=409, detail="Slot not available or lock busy, please retry!")

    return booking

@app.post("/bookings/2pc", response_model=FieldBookingResponse, status_code=201)
async def create_booking_2pc(data: FieldBookingRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    # VERIFICO IL CAMPO PRIMA DI ACQUISIRE IL LOCK
    field = await field_repository.get_by_id(db, data.field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found!")
    if not field.is_active:
        raise HTTPException(status_code=409, detail="Field not available!")
    lock = DistributedLock(redis)
    lock_key = f"field:{data.field_id}:{data.start_time.isoformat()}"
    token = await lock.acquire(lock_key, _2PC_LOCK_TTL_MS)
    if token is None:
        raise HTTPException(status_code=409, detail="Slot locked by concurrent request, please retry!")
    field_booking_id: Optional[int] = None
    utility_booking_ids: list[int] = []
    committed: bool = False

    try:
        # CONTROLLO OVERLAP DEL DB: PENDING E CONFIRMED BLOCCANO LO SLOT
        available = await field_booking_repository.check_availability(
            db,
            field_id = data.field_id,
            start_time = data.start_time,
            end_time = data.end_time,
        )
        if not available:
            raise HTTPException(status_code=409, detail="Slot already booked!")

        # CREA IL RECORD PENDING: GENERA IL TRANSACTION ID USATO DA TUTTO IL 2PC
        field_booking = await field_booking_repository.create_pending(
            db,
            field_id = data.field_id,
            user_id = data.user_id,
            start_time = data.start_time,
            end_time = data.end_time,
        )
        field_booking_id = field_booking.id

        print("\n" + "="*60)
        logger.info(">>> [2PC TRANSACTION START] txn_id=%s", field_booking_id)
        logger.info(">>> Booking Field %s for Users: %s", data.field_id, data.user_id)
        print("="*60)

        utility_ids = data.utility_ids or []

        # FASE 1 PREPARE: CHIEDE AD OGNI UTILITY DI VOTARE YES/NO E RACCOGLE GLI IDS
        logger.info("\n[PHASE 1] === PREPARE PHASE ===")
        logger.info("[2PC] Requesting votes from Utility Node at: %s", settings.utility_node_url)

        try:
            success, utility_booking_ids = await prepare_all(
                settings.utility_node_url,
                redis,
                field_booking_id,
                utility_ids
            )
        except Exception as e:
            print("\n" + "!"*60)
            logger.error("[!!!] NODE FAILURE DETECTED: Utility Node is Unreachable!")
            logger.error("[!!!] Error Details: %s", e)
            print("!"*60)
            raise HTTPException(status_code=503, detail="Utility Node Down, starting rollback")

        if not success:
            # ALMENO UN NO PRESENTE, ROLLBACK SU TUTTI I PARTECIPANTI GIA PRESENTI
            logger.warning("\n[PHASE 1] RESULT: Utility node Voted [ABORT/NO]")
            logger.info("[PHASE 2] === ROLLBACK PHASE (Abort) ===")

            await rollback_all(settings.utility_node_url, redis, field_booking_id, utility_booking_ids)
            await field_booking_repository.update_status(db, field_booking_id, BookingStatus.FAILED)
            await publish_booking_event(redis, "booking_failed", field_booking_id, data.field_id, "failed", data.user_id, data.start_time.isoformat(), data.end_time.isoformat())

            logger.info("[2PC TRANSACTION ABORTED] txn=%s ABORTED (prepare failed)", field_booking_id)
            raise HTTPException(status_code=409, detail="2PC Aborted: one or more utilities are unavailable!")

        #  SE SIAMO QUI ALLORA IL VOTO E' YES
        logger.info("\n[PHASE 1] RESULT: Utility Node voted [READY/YES]")
        logger.info("[PHASE 2] === COMMIT PHASE ===")

        # FASE COMMIT, PRIMA AGGIORNA IL DB LOCALE POI NOTIFICA I PARTECIPANTI
        await field_booking_repository.update_status(db, field_booking_id, BookingStatus.CONFIRMED)
        logger.info("[2PC] S1: Local Field Database -> Status: CONFIRMED")

        await commit_all(settings.utility_node_url, redis, field_booking_id, utility_booking_ids)
        logger.info("[2PC] S2: Global Commit sent to Utility Nodes")

        committed = True
        logger.info(">>> [2PC TRANSACTION SUCCESS] txn=%s COMMITTED", field_booking_id)
        print("="*60 + "\n")

        # NOTIFICO TUTTI I CLIENT WS CHE LO SLOT È CONFERMATO
        await publish_booking_event(redis, "booking_confirmed", field_booking_id, data.field_id, "confirmed", data.user_id, data.start_time.isoformat(), data.end_time.isoformat())

        updated_booking = await field_booking_repository.get_by_id(db, field_booking_id)
        return updated_booking

    except HTTPException:
        # ROLLBACK DI EMERGENZA SOLO SE IL BOOKING ESISTE MA NON È STATO COMMITTATO
        if field_booking_id is not None and not committed:
            fid: int = field_booking_id
            try:
                await rollback_all(settings.utility_node_url, redis, field_booking_id, utility_booking_ids)
                await field_booking_repository.update_status(db, field_booking_id, BookingStatus.FAILED)
            except Exception as inner:
                logger.error("[2PC] txn=%s rollback in except failed: %s", field_booking_id, inner)
        raise # RILANCIA SEMPRE AL CLIENT

    except Exception as exc:
        # ERRORE INATTESO: TENTA ROLLBACK BEST-EFFORT
        logger.error("[2PC] txn=%s unexpected error: %s", field_booking_id, exc)
        if field_booking_id is not None and not committed:
            try:
                await rollback_all(settings.utility_node_url, redis, field_booking_id, utility_booking_ids)
                await field_booking_repository.update_status(db, field_booking_id, BookingStatus.FAILED)
            except Exception as inner:
                logger.error("[2PC] txn=%s emergency failed: %s", field_booking_id, inner)
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}!")

    finally:
        # IL LOCK VIENE SEMPRE RILASCIATO, QUALUNQUE COSA ACCADA
        await lock.release(lock_key, token)

@app.websocket("/ws/availability")
async def ws_availability(websocket: WebSocket):
    await websocket.accept()
    logger.info("[WS] client connected!")

    pubsub_client = redis_manager.create_pubsub_client()
    pubsub = pubsub_client.pubsub()
    await pubsub.subscribe(AVAILABILITY_CHANNEL)

    async def _listen() -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception:
            pass

    task = asyncio.create_task(_listen())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("[WS] client disconnected!")
    finally:
        task.cancel()
        await pubsub.unsubscribe(AVAILABILITY_CHANNEL)
        await pubsub_client.aclose()
        logger.info("[WS] pubsub client closed!")

# ENDPOINT PER TRIGGERARE IL RECOVERY MANUALMENTE - UTILE PER DEMO E TEST
@app.post("/admin/recovery", status_code=200)
async def trigger_recovery():
    await run_recovery(settings.utility_node_url)
    return {"ok": True, "message": "Recovery job executed!"}