import json
import httpx
import pytest
import pytest_asyncio
import redis as redis_sync

FIELD_URL = "http://localhost:8001"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

@pytest.fixture(scope="module")
def redis_client():
    r = redis_sync.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    yield r
    r.close()

@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def prepared_booking_ids():
    async with httpx.AsyncClient(base_url=FIELD_URL) as client:
        field_resp = await client.post("/fields", json={
            "name": "Recovery Test Failed",
            "location": "Zone B",
            "sport_type": "basketball",
            "price_per_hour": 10.0,
        })
        assert field_resp.status_code == 201
        field_id = field_resp.json()["id"]

        booking_resp = await client.post("/bookings/2pc", json={
            "field_id": field_id,
            "user_id": "recovery_test_user",
            "start_time": "2040-06-01T10:00:00",
            "end_time": "2040-06-01T12:00:00",
            "utility_ids": []
        })
        assert booking_resp.status_code == 201
        booking_id = booking_resp.json()["id"]

    return  field_id, booking_id

@pytest.mark.asyncio(loop_scope="module")
class TestFaultTolerance:
    async def test_recovery_find_prepared_txn(self, redis_client, prepared_booking_ids):
        _, booking_id = prepared_booking_ids

        key = f"2pc:txn:{booking_id}"
        payload = json.dumps({"state": "prepared", "utility_booking_ids": []})
        redis_client.set(key, payload, ex=300)

        async with httpx.AsyncClient(base_url=FIELD_URL) as client:
            recovery_resp = await client.post("/admin/recovery")
            assert recovery_resp.status_code == 200
            assert recovery_resp.json()["ok"] is True

            booking_resp = await client.get(f"/bookings/{booking_id}")
            assert booking_resp.status_code == 200
            assert booking_resp.json()["status"] == "confirmed"

        raw = redis_client.get(key)
        assert raw is not None
        state = json.loads(raw)["state"]
        assert state == "committed"

    async def test_recovery_with_empty_redis(self, redis_client):
        for k in redis_client.scan_iter("2pc:txn:*"):
            redis_client.delete(k)

        async with httpx.AsyncClient(base_url=FIELD_URL) as client:
            resp = await client.post("/admin/recovery")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    async def test_recovery_aborts_if_utility_unreachable(self, redis_client):

        async with httpx.AsyncClient(base_url=FIELD_URL) as client:
            field_resp = await client.post("/fields", json={
                "name": "Abort Test Field",
                "location": "Zone P",
                "sport_type": "padel",
                "price_per_hour": 9.0,
            })
            assert field_resp.status_code == 201
            field_id = field_resp.json()["id"]

            booking_resp = await client.post("/bookings/2pc", json={
                "field_id": field_id,
                "user_id": "abort_test_user",
                "start_time": "2040-07-01T10:00:00",
                "end_time": "2040-07-01T12:00:00",
                "utility_ids": []
            })
            assert booking_resp.status_code == 201
            booking_id = booking_resp.json()["id"]

            key = f"2pc:txn:{booking_id}"
            payload = json.dumps({"state": "prepared", "utility_booking_ids": [99999]})
            redis_client.set(key, payload, ex=300)

            recovery_resp = await client.post("/admin/recovery")
            assert recovery_resp.status_code == 200

            booking_resp = await client.get(f"/bookings/{booking_id}")
            assert booking_resp.status_code == 200
            assert booking_resp.json()["status"] == "failed"

        raw = redis_client.get(key)
        assert raw is not None
        state = json.loads(raw)["state"]
        assert state == "aborted"

