import asyncio
import json
import logging
import httpx

from redis.asyncio import Redis
from db import db_manager
from redis_client import redis_manager
from repositories import field_booking_repository
from schemas import BookingStatus, TwoPCTransactionState
from two_pc_coordinator import commit_all, rollback_all

logger = logging.getLogger(__name__)

_RECOVERY_INTERVAL_S = 60  # OGNI QUANTI SECONDI GIRA IL JOB
_TXN_KEY_PREFIX = "2pc:txn:"
_HTTP_TIMEOUT = 5.0

async def _recover_one(
        redis: Redis,
        field_booking_id: int,
        utility_booking_ids: list[int],
        utility_node_url: str,
) -> None:
    # TENTO IL RE-COMMIT DI UNA SINGOLA TRANSAZIONE PRPARED, SE FALLISCE -> ABORTED + FAILED
    logger.warning("[RECOVERY] txn=%d found in PREPARED, try to re-commit | utility_booking_ids=%s", field_booking_id, utility_booking_ids)
    try:
        async with db_manager.session() as db:
            try:
                await commit_all(utility_node_url, redis, field_booking_id, utility_booking_ids)
                await field_booking_repository.update_status(db, field_booking_id, BookingStatus.CONFIRMED)
                logger.info("[RECOVERY] txn=%d re-commit OK -> CONFIRMED !", field_booking_id)
            except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
                # SE UTILITY NODE NON RISPONDE NON POSSO COMPLETARE -> ABORT
                logger.error("[RECOVERY] txn=%d re-commit failed (%s) -> ABORTED + FAILED !", field_booking_id, exc)
                await  rollback_all(utility_node_url, redis, field_booking_id, utility_booking_ids)
                await field_booking_repository.update_status(db, field_booking_id, BookingStatus.FAILED)
    except Exception as exc:
        logger.error("[RECOVERY] txn=%d unexpected error: %s", field_booking_id, exc)

async def run_recovery(utility_node_url: str) -> None:
    # SCANSIONO REDIS CERCANDO LE TRANSAZIONI IN STATO PREPARED PER RECUPERARLE
    redis = redis_manager.get_redis()
    cursor = 0
    recovered = 0

    try:
        # SCAN INCREMENTALE, NON BLOCCO IL SERVER DURANTE LA DURATA DELLA SCANSIONE
        while True:
            cursor, keys = await redis.scan(cursor, match=f"{_TXN_KEY_PREFIX}*", count=100)
            for key in keys:
                raw = await redis.get(key)
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("state") != TwoPCTransactionState.PREPARED.value:
                    continue

                # ESTRAGGO IL FIELD_BOOKING_ID DALLA CHIAVE "2pc:txn:{id}"
                field_booking_id = int(key.removeprefix(_TXN_KEY_PREFIX))
                utility_booking_ids = data.get("utility_booking_ids", [])

                await _recover_one(redis, field_booking_id, utility_booking_ids, utility_node_url)
                recovered += 1

                if cursor == 0:
                    break

            if recovered == 0:
                logger.debug("[RECOVERY] no PREPARED transaction found!")
            else:
                logger.debug("[RECOVERY] job completed: %d transaction recovered!", recovered)
    except Exception as exc:
        logger.error("[RECOVERY] errore while Redis scanning: %s", exc)

async def recovery_loop(utility_node_url: str):
    # LOOP INFINITO CHE CHIAMA RUN_RECOVRY OGNI 60 SECONDI, AVVIATO COME ASYNCIO.CREATE_TASK
    logger.info("[RECOVERY] background loop started (interval=%ds)", _RECOVERY_INTERVAL_S)
    while True:
        await asyncio.sleep(_RECOVERY_INTERVAL_S)
        await run_recovery(utility_node_url)