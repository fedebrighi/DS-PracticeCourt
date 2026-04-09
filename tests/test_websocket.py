import asyncio
import time
from datetime import datetime, timezone, timedelta
import httpx
import pytest
import websockets
import json

FIELD_URL = "http://localhost:8001"
UTILITY_URL = "http://localhost:8002"
WS_URL = "ws://localhost:8001/ws/availability"
_BASE_TS = int(time.time())
_WS_TIMEOUT = 5.0

def _slot_ws(offset_hours: int = 0):
    base = datetime(2035, 1, 1, 10 + offset_hours, 0, 0, tzinfo = timezone.utc)
    return base.isoformat(), (base + timedelta(hours=1)).isoformat()   # START E END

@pytest.fixture(scope="module")
def active_field_id():
    r = httpx.post(f"{FIELD_URL}/fields", json={
        "name": f"Campo WS {_BASE_TS}",
        "sport_type": "Football",
        "location": "Zone F",
        "price_per_hour": 8.0,
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()["id"]

@pytest.fixture(scope="module")
def active_utility_id():
    r = httpx.post(f"{UTILITY_URL}/utilities", json={
        "name": f"Luci WS {_BASE_TS}",
        "sport_type": "Lighting",
        "price_per_hour": 4.0,
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()["id"]

class TestWebSocket:

    @pytest.mark.asyncio
    async def test_ws_receives_booking_confirmed(self, active_field_id):
        # APRO LA WS PRIMA DELLA POST, L'EVENTO DEVE ESSERE GIA IN ASCOLTO QUANDO VIENE PUBBLICATO
        start, end = _slot_ws(0)
        async with websockets.connect(WS_URL) as ws:
            r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
                "field_id": active_field_id,
                "user_id": f"test_ws_{_BASE_TS}",
                "start_time": start,
                "end_time": end,
                "utility_ids": [],
            })
            assert r.status_code == 201

            # ASPETTO IL MESSAGGIO WS, SE NON ARRIVA ENTRO I 5 SECONDI FALLISCE
            raw = await asyncio.wait_for(ws.recv(), timeout=_WS_TIMEOUT)
            event = json.loads(raw)

        assert event["event_type"] == "booking_confirmed"
        assert event["field_id"] == active_field_id
        assert event["status"] == "confirmed"
        assert "field_booking_id" in event
        assert "timestamp" in event

    @pytest.mark.asyncio
    async def test_ws_multiple_clients_all_receive(self, active_field_id):
        # DUE CLIENT CONNESSI CONTEMPORANEAMENTE DEVONO RICEVERE ENTRAMBI L'EVENTO
        start, end = _slot_ws(2)
        async with websockets.connect(WS_URL) as ws1, \
                websockets.connect(WS_URL) as ws2:
            r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
                "field_id": active_field_id,
                "user_id": f"test_ws_multi_{_BASE_TS}",
                "start_time": start,
                "end_time": end,
                "utility_ids": [],
            })
            assert r.status_code == 201

            # ENTRAMBI I CLIENT DEVONO RICEVERE L'EVENTO IN PARALLELO
            raw1, raw2 = await asyncio.wait_for(
                asyncio.gather(ws1.recv(), ws2.recv()),
                timeout=_WS_TIMEOUT,
            )
            event1 = json.loads(raw1)
            event2 = json.loads(raw2)

        assert event1["event_type"] == "booking_confirmed"
        assert event2["event_type"] == "booking_confirmed"
        assert event1["field_booking_id"] == event2["field_booking_id"]

    @pytest.mark.asyncio
    async def test_ws_receives_booking_failed(self, active_field_id):
        # CON UTILITY INESISTENTE, VOTA NO ALLA PREPARE E SI VA AL ROLLBACK
        start, end = _slot_ws(1)
        async with websockets.connect(WS_URL) as ws:
            r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
                "field_id": active_field_id,
                "user_id": f"test_ws_fail{_BASE_TS}",
                "start_time": start,
                "end_time": end,
                "utility_ids": [99999],  # ID INESISTENTE
            })
            assert r.status_code == 409

            # ASPETTO IL MESSAGGIO WS, SE NON ARRIVA ENTRO I 5 SECONDI FALLISCE
            raw = await asyncio.wait_for(ws.recv(), timeout=_WS_TIMEOUT)
            event = json.loads(raw)

        assert event["event_type"] == "booking_failed"
        assert event["field_id"] == active_field_id
        assert event["status"] == "failed"
