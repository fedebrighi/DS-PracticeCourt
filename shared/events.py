import logging
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis
import json

logger = logging.getLogger(__name__)

# CANALE REDIS SU CUI VENGONO PUBBLICATI GLI EVENTI DI DISPONIBILITÀ
AVAILABILITY_CHANNEL = "availability_updates"

async def publish_booking_event(
        redis: Redis,
        event_type: str,
        field_booking_id: Optional[int],
        field_id: int,
        status: str,
        user_id: str,
        start_time: str,
        end_time: str
) -> None:
    # COSTRUISCO IL PAYLOAD JSON CON I DATI ESSENZIALI PER AGGIORNARE LA UI
    payload = json.dumps({
        "event_type": event_type,
        "field_booking_id": field_booking_id,
        "field_id": field_id,
        "status": status,
        "user_id": user_id,
        "start_time": start_time,
        "end_time": end_time,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    try:
        await redis.publish(AVAILABILITY_CHANNEL, payload)
        logger.info(
            "[EVENTS] published event_type=%s field_booking_id=%s, field_id=%s",
            event_type, field_booking_id, field_id
        )
    except Exception as exc:
        logger.error("[EVENTS] publish failed: %s", exc)
