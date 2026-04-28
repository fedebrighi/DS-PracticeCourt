import asyncio
import json
import time
import httpx
import pytest
import pytest_asyncio
import websockets
from redis.asyncio import Redis as AsyncRedis

FIELD_URL = "https://localhost:8001"
WS_URL = "ws://localhost:8001/ws/availability"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

_BASE_TS = int(time.time())
_WS_TIMEOUT = 5.0
_HOLD_DATE = "2035-08.01"
_HOLD_TTL_S = 60

# CLIENT REDIS PER EFFETTUARE LE VARIE VERIFICHE
@pytest_asyncio.fixture(scope="module")
async def redis_client():
    r = AsyncRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses = True)
    yield r
    await r.aclose()

# UNICO CAMPO CREATO PER I TEST
@pytest.fixture(scope="module")
def hold_field_id():
    resp = httpx.post(
        f"{FIELD_URL}/fields",
        json = {
            "name": f"Hold Test Field {_BASE_TS}",
            "sport_type": "football",
            "location": "Zone F",
            "price_per_hour": 8.0,
            "is_active": True,
        },
    )
    assert resp.status_code == 201, f"Cannot create hold field: {resp.text}"
    return resp.json()["id"]

def _hold_msg(user_id: str, field_id: int, slots: list) -> str:
    return json.dumps({
        "action": "hold_slots",
        "user_id": user_id,
        "field_id": field_id,
        "date": _HOLD_DATE,
        "slots": slots,
    })

def _release_msg(user_id: str, field_id: int, slots: list) -> str:
    return json.dumps({
        "action": "release_slots",
        "user_id": user_id,
        "field_id": field_id,
        "date": _HOLD_DATE,
        "slots": slots,
    })

def _hold_key(field_id: int, slot: str) -> str:
    return f"Hold:{field_id}:{_HOLD_DATE}:{slot}"

@pytest.mark.asyncio(loop_scope="module")
class TestTemporaryHold:

    # HOLD PROPAGATO A TUTTI I CLIENT (MITTENTE INCLUSO)
    async def test_hold_slots_broadcast_to_all_clients(self, hold_field_id):
        slot = "10.00"
        user_a = f"user_hold_a_{_BASE_TS}"

        async with (websockets.connect(WS_URL) as ws_a, websockets.connect(WS_URL) as ws_b):
            await ws_a.send(_hold_msg(user_a, hold_field_id, [slot]))

            # ENTRAMBI I CLIENT RICEVONO L EVENTO IN PARALLELO
            raw_a, raw_b = await asyncio.wait_for(asyncio.gather(ws_a.recv(), ws_b.recv()), timeout=_WS_TIMEOUT)
            event_a = json.loads(raw_a)
            event_b = json.loads(raw_b)

            # LO STESSO EVENTO QUINDI STESSI DATI SU ENTRAMBI I CLIENT
            for event in (event_a, event_b):
                assert event["event_type"] == "slots_held"
                assert event["field_id"] == hold_field_id
                assert slot in event["slots"]
                assert event["user_id"] == user_a
                assert event["date"] == _HOLD_DATE


    # RELEASE PROPAGATO A TUTTI I CLIENT
    async def test_release_slots_broadcast_to_all_clients(self, hold_field_id):
        slot = "11:00"
        user_a = f"user_release_{_BASE_TS}"

        async with (websockets.connect(WS_URL) as ws_a, websockets.connect(WS_URL) as ws_b):
            # HOLD
            await ws_a.send(_hold_msg(user_a, hold_field_id, [slot]))
            await asyncio.wait_for(asyncio.gather(ws_a.recv(), ws_b.recv()), timeout=_WS_TIMEOUT)

            # RELEASE
            await ws_a.send(_release_msg(user_a, hold_field_id, [slot]))
            raw_a, raw_b = await asyncio.wait_for(asyncio.gather(ws_a.recv(), ws_b.recv()), timeout=_WS_TIMEOUT)
            event_a = json.loads(raw_a)
            event_b = json.loads(raw_b)

            for event in (event_a, event_b):
                assert event["event_type"] == "slots_released"
                assert event["field_id"] == hold_field_id
                assert slot in event["slots"]
                assert event["user_id"] == user_a

    # HOLD SCRIVE LA CHIAVE REDIS CON IL TTL CORRETTO
    async def test_hold_writes_redis_key_with_correct_ttl(self, hold_field_id, redis_client):
        slot = "12.00"
        key = _hold_key(hold_field_id, slot)
        await redis_client.delete(key)

        async with websockets.connect(WS_URL) as ws_a:
            await ws_a.send(_hold_msg(f"user_redis_{_BASE_TS}", hold_field_id, [slot]))
            await asyncio.wait_for(ws_a.recv(), timeout=_WS_TIMEOUT)

        exists = await redis_client.exists(key)
        assert exists == 1, f"Redis Key '{key}' not found after hold_slots"

        ttl = await redis_client.exists(key)
        assert 50 <= ttl <= _HOLD_TTL_S

    # RELEASE RIMUOVE LA CHIAVE REDIS CREATA
    async def test_release_removes_redis_key(self, hold_field_id, redis_client):
        slot = "13:00"
        key = _hold_key(hold_field_id, slot)
        user_a = f"user_release_redis_{_BASE_TS}"
        await redis_client.delete(key)

        async with websockets.connect(WS_URL) as ws_a:
            # HOLD: CREO LA CHIAVE
            await ws_a.send(_hold_msg(user_a, hold_field_id, [slot]))
            await asyncio.wait_for(ws_a.recv(), timeout=_WS_TIMEOUT)
            exists_after_hold = await redis_client.exists(key)

            # RELEASE: RIMUOVO LA CHIAVE
            await ws_a.send(_release_msg(user_a, hold_field_id, [slot]))
            await asyncio.wait_for(ws_a.recv(), timeout=_WS_TIMEOUT)
            exists_after_release = await redis_client.exists(key)

        assert exists_after_hold ==1
        assert exists_after_release == 0

    # GET /bookings/holds DEVE RESTITUIRE GLI SLOT ATTIVI
    async def test_get_holds_endpoint_returns_active_holds(self, hold_field_id, redis_client):
        slot = "14.00"
        key = _hold_key(hold_field_id, slot)
        user_id = f"user_holds_ep_{_BASE_TS}"
        await redis_client.delete(key)

        async with websockets.connect(WS_URL) as ws_a:
            await ws_a.send(_hold_msg(user_id, hold_field_id, [slot]))
            await asyncio.wait_for(ws_a.recv(), timeout=_WS_TIMEOUT)

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{FIELD_URL}/bookings/holds", params={"field_id": hold_field_id, "date": _HOLD_DATE})
            assert resp.status_code == 200
            holds = resp.json()

        assert slot in holds, f"Slot {slot} not found in response: {holds}"
        assert holds[slot] == user_id

    # PIÙ SLOT MANTENUTI IN UN SINGOLO MESSAGGIO
    async def test_multiple_slots_in_single_hold_message(self, hold_field_id, redis_client):
        slots = ["15:00", "16:00", "17:00"]
        user_id = f"user_multi_slot_{_BASE_TS}"
        keys = [_hold_key(hold_field_id, s) for s in slots]

        for k in keys:
            await redis_client.delete(k)

        async with websockets.connect(WS_URL) as ws_a:
            await ws_a.send(_hold_msg(user_id, hold_field_id, slots))
            raw = await asyncio.wait_for(ws_a.recv(), timeout=_WS_TIMEOUT)
            event = json.loads(raw)

        assert event["event_type"] == "slots_held"
        assert set(event["slots"]) == set(slots)

        for slot, key in zip(slots, keys):
            exists = await redis_client.exists(key)
            assert exists == 1, f"Redis Key missing for slot {slot}: {key}"

    # LA SCADENZA DEL TTL RENDE LO SLOT NUOVAMENTE DISPONIBILE
    async def test_hold_expiry_slot_becomes_available(self, hold_field_id, redis_client):
        slot = "18:00"
        key = _hold_key(hold_field_id, slot)

        await redis_client.set(key, f"user_expiry_{_BASE_TS}", ex=2)

        exists_before = await redis_client.exists(key)
        assert exists_before == 1
        await asyncio.sleep(3)

        exists_after = await redis_client.exists(key)
        assert exists_after == 0

    # PIÙ UTENTI TENGONO SLOT DIVERSI CONTEMPORANEAMENTE
    async def test_multiple_users_hold_different_slots(self, hold_field_id, redis_client):
        slot_a, slot_b = "19:00", "20:00"
        user_a = f"user_multi_a_{_BASE_TS}"
        user_b = f"user_multi_b_{_BASE_TS}"
        key_a = _hold_key(hold_field_id, slot_a)
        key_b = _hold_key(hold_field_id, slot_b)
        await redis_client.delete(key_a, key_b)

        async with (websockets.connect(WS_URL) as ws_a, websockets.connect(WS_URL) as ws_b):
            # A TIENE slot_a: A E B RICEVONO ENTRAMBI SLOT
            await ws_a.send(_hold_msg(user_a, hold_field_id, [slot_a]))
            raw_from_a_a, raw_from_a_b = await asyncio.wait_for(asyncio.gather(ws_a.recv(), ws_b.recv()), timeout=_WS_TIMEOUT)

            # SPECULARE MA CON B
            await ws_b.send(_hold_msg(user_b, hold_field_id, [slot_b]))
            raw_from_b_a, raw_from_b_b = await asyncio.wait_for(asyncio.gather(ws_a.recv(), ws_b.recv()), timeout=_WS_TIMEOUT)

            await asyncio.sleep(0.3)
            exists_a = await redis_client.exists(key_a)
            exists_b = await redis_client.exists(key_b)

        # CONTROLLI EVENTI
        ev_b_sees_a = json.loads(raw_from_a_b)
        ev_a_sees_b = json.loads(raw_from_b_a)

        assert ev_b_sees_a["event_type"] == "slots_held"
        assert slot_a in ev_b_sees_a["slots"]
        assert ev_b_sees_a["user_id"] == user_a

        assert ev_a_sees_b["event_type"] == "slots_held"
        assert slot_b in ev_a_sees_b["slots"]
        assert ev_a_sees_b["user_id"] == user_b

        assert exists_a == 1, f"Redis Key {key_a} not found"
        assert exists_b == 1, f"Redis Key {key_b} not found"

    # CANCELLANDO LA PRENOTAZIONE INVIO booking_canceled VIA WEBSOCKET
    async def test_cancel_booking_send_ws_event(self, hold_field_id):
        start = "2035-09-01T10:00:00+00:00"
        end   = "2035-09-01T11:00:00+00:00"

        booking_resp = httpx.post(
            f"{FIELD_URL}/bookings/2pc",
            json={
                "field_id": hold_field_id,
                "user_id": f"user_cancel_{_BASE_TS}",
                "start_time": start,
                "end_time": end,
                "utility_ids": [],
            },
        )
        assert booking_resp.status_code == 201, f"Cannot create booking for cancel test: {booking_resp.text}"
        booking_id = booking_resp.json()["id"]

        async with websockets.connect(WS_URL) as ws_observer:
            async with httpx.AsyncClient() as client:
                del_resp = await client.delete(f"{FIELD_URL}/bookings/{booking_id}")
            assert del_resp.status_code == 200
            assert del_resp.json()["ok"] is True

            raw = await asyncio.wait_for(ws_observer.recv(), timeout=_WS_TIMEOUT)
            event = json.loads(raw)

        assert event["event_type"] == "booking_cancelled"
        assert event["field_id"] == hold_field_id
        assert event["status"] == "cancelled"

        check = httpx.get(f"{FIELD_URL}/bookings/{booking_id}")
        assert check.status_code == 200
        assert check.json()["status"] == "cancelled"
