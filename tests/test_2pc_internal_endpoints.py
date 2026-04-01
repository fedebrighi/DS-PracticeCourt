import time

import pytest
import httpx

UTILITY_BASE = "http://localhost:8002"

# CREO UNA UTILITY ATTIVA E UNA INATTIVA PRIMA DI FARE I TEST

@pytest.fixture(scope="module")
def active_utility_id() -> int:
    with httpx.Client() as client:
        resp = client.post(f"{UTILITY_BASE}/utilities", json={
            "name": "Test Lighting 2PC",
            "utility_type": "lighting",
            "price_per_hour": 5.0,
        })
        assert resp.status_code == 201
        return resp.json()["id"]

@pytest.fixture(scope="module")
def inactive_utility_id() -> int:
    return 99999

# CON UNA UTILITY ATTIVA DEVO AVERE VOTO YES CON ID VALIDO
def test_prepare_active_utility_votes_yes(active_utility_id):
    with httpx.Client() as client:
        resp = client.post(f"{UTILITY_BASE}/internal/prepare", json={
            "field_booking_id": 1001,
            "utility_id": active_utility_id,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["vote"] == "yes"
    assert body["utility_booking_id"] is not None
    assert isinstance(body["utility_booking_id"], int)

# CON UTILITY NON ATTIVA DEVO AVERE VOTO NO E NESSUN ID
def test_prepare_nonexistent_utility_votes_no(inactive_utility_id):
    with httpx.Client() as client:
        resp = client.post(f"{UTILITY_BASE}/internal/prepare", json={
            "field_booking_id": 1002,
            "utility_id": inactive_utility_id,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["vote"] == "no"
    assert body["utility_booking_id"] is None
    assert body["reason"] is not None

# DOPO IL PREPARE LA UTILITY BOOKING DEVE ESSERE PENDING NEL DB
def test_prepare_creates_pending_booking(active_utility_id):
    field_booking_id = int(time.time())
    with httpx.Client() as client:
        resp = client.post(f"{UTILITY_BASE}/internal/prepare", json={
            "field_booking_id": field_booking_id,
            "utility_id": active_utility_id,
        })
    assert resp.status_code == 200
    assert resp.json()["vote"] == "yes"

    with httpx.Client() as client:
        bookings = client.get(f"{UTILITY_BASE}/utility-bookings/by-field-booking/{field_booking_id}")
    assert resp.status_code == 200
    results = bookings.json()
    assert len(results) == 1
    assert results[0]["status"] == "pending"

# DOPO AVERE FATTO PREPARE + COMMIT LA UTILITY BOOKING DEVE ESSERE CONFIRMED
def test_commit_updates_status_to_confirmed(active_utility_id):
    field_booking_id = 2001
    with httpx.Client() as client:
        prep = client.post(f"{UTILITY_BASE}/internal/prepare", json={
            "field_booking_id": field_booking_id,
            "utility_id": active_utility_id,
        })
    assert prep.json()["vote"] == "yes"
    ub_id = prep.json()["utility_booking_id"]

    with httpx.Client() as client:
        commit = client.post(f"{UTILITY_BASE}/internal/commit", json={
            "field_booking_id": field_booking_id,
            "utility_booking_ids": [ub_id],
        })
    assert commit.status_code == 200
    assert commit.json()["ok"] is True

    with httpx.Client() as client:
        bookings = client.get(f"{UTILITY_BASE}/utility-bookings/by-field-booking/{field_booking_id}")

    results = bookings.json()
    assert results[0]["status"] == "confirmed"

# DOPO PREPARE + ROLLBACK LA UTILITY BOOKING DEVE ESSERE CANCELLED
def test_rollback_updates_status_to_cancelled(active_utility_id):
    field_booking_id = int(time.time())
    with httpx.Client() as client:
        prep = client.post(f"{UTILITY_BASE}/internal/prepare", json={
            "field_booking_id": field_booking_id,
            "utility_id": active_utility_id,
        })
    assert prep.json()["vote"] == "yes"
    ub_id = prep.json()["utility_booking_id"]

    with httpx.Client() as client:
        rollback = client.post(f"{UTILITY_BASE}/internal/rollback", json={
            "field_booking_id": field_booking_id,
            "utility_booking_ids": [ub_id],
        })
    assert rollback.status_code == 200
    assert rollback.json()["ok"] is True

    with httpx.Client() as client:
        bookings = client.get(f"{UTILITY_BASE}/utility-bookings/by-field-booking/{field_booking_id}")
    results = bookings.json()

    # CERCO IL BOOKING SPECIFICO PER ub_id
    target = next(r for r in results if r["id"] == ub_id)
    assert target["status"] == "cancelled"

# SE FACCIO ROLLBACK CON UNA LISTA VUOTA -> OK DEVE ESSERE TRUE, NON DEVO ANNULLARE NESSUNA UTILITY
def test_rollback_empty_ids_returns_ok():
    with httpx.Client() as client:
        resp = client.post(f"{UTILITY_BASE}/internal/rollback", json={
            "field_booking_id": 9999,
            "utility_booking_ids": []
        })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
