import asyncio
import time
from datetime import tzinfo, timedelta

import httpx
import pytest
from django.db.models.functions import datetime

FIELD_NODE_URL = "http://localhost:8001"
UTILITY_NODE_URL = "http://localhost:8002"
N_CONCURRENT = 10  # NUMERO DI  RICHIESTE CHE MANDERO' COME TEST
_BASE_TS = int(time.time())

# GENERA UNO SLOT FUTURO DINAMICO
def _future_slot(hour: int = 10):
    base = datetime(2035, 1, 1, hour, 0, 0, tzinfo=time.timezone.utc)
    return base.isoformat(), (base + timedelta(hours = 1)).isoformat()

async def create_test_field(client: httpx.AsyncClient, suffix: str = "") -> int:   # CREO UN CAMPO DI TEST
    response = await client.post(
        f"{FIELD_NODE_URL}/fields",
        json={
            "name": f"Test Concurrency Field {_BASE_TS}{suffix}",
            "sport_type": "football",
            "location": "Zone F",
            "price_per_hour": 20.0,
        },
    )
    assert response.status_code == 201, f"Cannot create the field: {response.text}"
    field_id = response.json()["id"]
    print(f"Test field successfully created with ID: {field_id}")
    return field_id

# PROVO A FARE LA PRENOTAZIONE AL CAMPO CREATO
async def try_book_simple(client: httpx.AsyncClient, field_id: int, user_id: str, start: str, end: str) -> dict:
    payload = {
        "field_id": field_id,
        "user_id": user_id,
        "start_time": start,
        "end_time": end,
    }
    response = await client.post(
        f"{FIELD_NODE_URL}/bookings",
        json=payload,
        timeout=10.0,
    )
    return {
        "user_id": user_id,
        "status_code": response.status_code,
    }

async def _try_book_2pc(client: httpx.AsyncClient, field_id: int, user_id: str, utility_ids: list, start: str, end: str,)-> dict:
    resp = await client.post(f"{FIELD_NODE_URL}/bookings/2pc", json={
        "field_id": field_id,
        "user_id": user_id,
        "start_time": start,
        "end_time": end,
        "utility_ids": utility_ids,
    }, timeout=10.)
    return {"user_id": user_id, "status_code": resp.status_code}

# VERIFICA CHE CI SIA 1 VINCITORE E TUTTI GLI ALTRI CONFLITTI
def _assert_one_winner(results: list, label: str):
    successes = [r for r in results if r["status_code"] == 201]
    conflicts = [r for r in results if r["status_code"] == 409]
    errors = [r for r in results if r["status_code"] not in (201, 409)]

    assert len(errors) == 0, (
        f"[{label}] {len(errors)} responses with unexpected status: "
        f"{[r['status_code'] for r in errors]}"
    )

    assert len(successes) == 1, (
        f"[{label}] Expected 1 winning booking, got {len(successes)}."
        "Distributed Lock Not Working!"
    )

    assert len(conflicts) == N_CONCURRENT - 1, (
        f"[{label}] Expected {N_CONCURRENT - 1} conflicts, got {len(conflicts)}."
    )

@pytest.mark.asyncio
# N UTENTI PRENOTANO LO STESSO SLOT, SOLO 1 DEVE VINCERE
async def test_concurrent_booking_simple():
    start, end = _future_slot(hour=10)
    async with httpx.AsyncClient() as client:
        field_id = await create_test_field(client, "_simple")
        tasks = [
            try_book_simple(client, field_id, f"user_simple_{i}", start, end)
            for i in range(N_CONCURRENT)
        ]
        results = await asyncio.gather(*tasks)
    _assert_one_winner(results, "/bookings simple")

@pytest.mark.asyncio
# N UTENTI PRENOTANO LO STESSO 2PC SLOT SENZA UTILITY, SOLO 1 DEVE VINCERE
async def test_concurrent_booking_2pc_no_utility():
    start, end = _future_slot(hour=12)
    async with httpx.AsyncClient() as client:
        field_id = await create_test_field(client, "_2pc")
        tasks = [
            _try_book_2pc(client, field_id, f"user_2pc_{i}", [], start, end)
            for i in range(N_CONCURRENT)
        ]
        results = await asyncio.gather(*tasks)
    _assert_one_winner(results, "/bookings/2pc no utility")

@pytest.mark.asyncio
# N UTENTI PRENOTANO LO STESSO 2PC SLOT CON UTILITY, SOLO 1 DEVE VINCERE
async def test_concurrent_booking_2pc_with_utility():
    start, end = _future_slot(hour=14)
    async with httpx.AsyncClient() as client:
        field_id = await create_test_field(client, "_2pc_util")

        util_resp = await client.post(
            f"{UTILITY_NODE_URL}/utilities",
            json={
                "name": f"Lights {_BASE_TS}",
                "utility_type": "lighting",
                "price_per_hour": 5.0,
                "is_active": True
            },
        )
        assert util_resp.status_code == 201, f"Cannot create utility: {util_resp.text}"
        utility_id = util_resp.json()["id"]

        tasks = [
            _try_book_2pc(client, field_id, f"user_2pc_util{i}", [utility_id], start, end)
            for i in range(N_CONCURRENT)
        ]
        results = await asyncio.gather(*tasks)
    _assert_one_winner(results, "/bookings/2pc with utility")

    # VERIFICO INFINE CHE L UTILITY BOOKING DEL VINCITORE DEVE ESSERE CONFIRMED
    async with httpx.AsyncClient() as client:
        all_bookings = (await client.get(f"{FIELD_NODE_URL}/bookings")).json()
        winner_booking = next((b for b in all_bookings if b["field_id"] == field_id and b["status"] == "confirmed"), None)
        assert winner_booking is not None, "No Confirmed Booking found after the race"
