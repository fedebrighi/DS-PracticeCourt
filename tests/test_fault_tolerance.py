import json
import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis as AsyncRedis

FIELD_URL = "http://localhost:8001"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# CLIENT REDIS ASINCRONO USATO SOLO NEI TEST PER INIETTARE STATI DIRETTAMENTE
# SERVE SOLO PER SETUP/TEARDOWN DEI TEST
@pytest_asyncio.fixture(scope="module")
async def redis_client():
    # DECODE_RESPONSES TRUE PER LAVORARE CON STRINGHE INVECE DI BYTES
    r = AsyncRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    yield r
    await r.aclose()

# CREA UN FIELD E UN BOOKING PENDING NEL DB E RESTITUISCE IL BOOKING ID
@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def prepared_booking_ids():
    async with httpx.AsyncClient(base_url=FIELD_URL, timeout=10.0) as client:
        # CREO IL CAMPO
        field_resp = await client.post("/fields", json={
            "name": "Recovery Test Failed",
            "location": "Zone B",
            "sport_type": "basketball",
            "price_per_hour": 10.0,
        })
        assert field_resp.status_code == 201
        field_id = field_resp.json()["id"]

        # CREO IL BOOKING IN STATO PENDING CON CHIAMATA 2PC
        booking_resp = await client.post("/bookings/2pc", json={
            "field_id": field_id,
            "user_id": "recovery_test_user",
            "start_time": "2040-06-01T10:00:00",
            "end_time": "2040-06-01T12:00:00",
            "utility_ids": []
        })
        assert booking_resp.status_code == 201
        booking_id = booking_resp.json()["id"]

    yield  field_id, booking_id
    r = AsyncRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    await r.delete(f"2pc:txn:{booking_id}")
    await r.aclose()

@pytest.mark.asyncio(loop_scope="module")
class TestFaultTolerance:
    async def test_recovery_find_prepared_txn(self, redis_client, prepared_booking_ids):
        # SCENARIO IN CUI IL COORDINATORE CRASHA DOPO IL PREPARED
        # IL RECOVERY DEVE COMPLETARE IL COMMIT
        _, booking_id = prepared_booking_ids

        # INIETTA LO STATO PREPARED IN REDIS, SIMULA IL CRASH DOPO LA PREPARE PHASE
        key = f"2pc:txn:{booking_id}"
        payload = json.dumps({"state": "prepared", "utility_booking_ids": []})
        await redis_client.set(key, payload, ex=300)

        # TRIGGERO IL RECOVERY JOB MANUALMENTE
        async with httpx.AsyncClient(base_url=FIELD_URL, timeout=10.0) as client:
            recovery_resp = await client.post("/admin/recovery")
            assert recovery_resp.status_code == 200
            assert recovery_resp.json()["ok"] is True

            # VERIFICO CHE IL BOOKING SIA STATO PORTATO A CONFIRMED DAL RECOVERY
            booking_resp = await client.get(f"/bookings/{booking_id}")
            assert booking_resp.status_code == 200
            assert booking_resp.json()["status"] == "confirmed"

        # VERIFICO ANCHE CHE LA CHIAVE REDIS SIA STATA AGGIORNATA A COMMITTED
        raw = await redis_client.get(key)
        assert raw is not None
        state = json.loads(raw)["state"]
        assert state == "committed"

    async def test_recovery_with_empty_redis(self, redis_client):
        # SCENARIO IN CUI NON HO TRANSAZIONI BLOCCATE
        async for k in redis_client.scan_iter("2pc:txn:*"):
            await redis_client.delete(k)

        async with httpx.AsyncClient(base_url=FIELD_URL, timeout=10.0) as client:
            resp = await client.post("/admin/recovery")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    async def test_recovery_aborts_if_utility_unreachable(self, redis_client):
        # SCENARIO IN CUI HO UNA TRANSAZIONE PREPARED MA CON UTILITY BOOKING INESISTENTE
        # RECOVERY DOVRÀ DARMI ABORTED + FAILED
        async with httpx.AsyncClient(base_url=FIELD_URL, timeout=10.0) as client:
            # CREO CAMPO
            field_resp = await client.post("/fields", json={
                "name": "Abort Test Field",
                "location": "Zone P",
                "sport_type": "padel",
                "price_per_hour": 9.0,
            })
            assert field_resp.status_code == 201
            field_id = field_resp.json()["id"]

            # CREO BOOKING
            booking_resp = await client.post("/bookings/2pc", json={
                "field_id": field_id,
                "user_id": "abort_test_user",
                "start_time": "2040-07-01T10:00:00",
                "end_time": "2040-07-01T12:00:00",
                "utility_ids": []
            })
            assert booking_resp.status_code == 201
            booking_id = booking_resp.json()["id"]

            # INIETTO PREPARED MA CON ID INESISTENTE
            key = f"2pc:txn:{booking_id}"
            payload = json.dumps({"state": "prepared", "utility_booking_ids": [99999]})
            await redis_client.set(key, payload, ex=300)

            recovery_resp = await client.post("/admin/recovery")
            assert recovery_resp.status_code == 200

            # BOOKING FALLITO
            booking_resp = await client.get(f"/bookings/{booking_id}")
            assert booking_resp.status_code == 200
            assert booking_resp.json()["status"] == "failed"

        # STATO REDIS ABORTED
        raw = await redis_client.get(key)
        assert raw is not None
        state = json.loads(raw)["state"]
        assert state == "aborted"

        await redis_client.delete(key)

