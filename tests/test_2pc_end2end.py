from datetime import datetime, timezone, timedelta
import time
import httpx
import pytest

FIELD_URL = "http://localhost:8001"
UTILITY_URL = "http://localhost:8002"
_BASE_TS = int(time.time())

# UNICO SLOT TEMPORALE COMUNE
def _slot(offset_hours: int = 0):
    base = datetime(2030, 6, 1, 10 + offset_hours, 0, 0, tzinfo = timezone.utc)
    return base.isoformat(), (base + timedelta(hours=1)).isoformat()

# CREO UN CAMPO
@pytest.fixture(scope="module")
def active_field_id():
    r = httpx.post(f"{FIELD_URL}/fields", json={
        "name": f"Campo E2E {_BASE_TS}",
        "sport_type": "Football",
        "location": "Zone F",
        "price_per_hour": 10.0,
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()["id"]

# CREO UNA UTILITY
@pytest.fixture(scope="module")
def active_utility_id():
    r = httpx.post(f"{UTILITY_URL}/utilities", json={
        "name": f"Luci E2E {_BASE_TS}",
        "utility_type": "Lighting",
        "price_per_hour": 5.0,
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()["id"]

class TestTwoPCEndToEnd:
    # CON CAMPO + UTILITY ATTIVI -> CONFIRMED
    def test_2pc_commit_success(self, active_field_id, active_utility_id):
        start, end = _slot(0)
        r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
            "field_id": active_field_id,
            "user_id": "user_e2e_1",
            "start_time": start,
            "end_time": end,
            "utility_ids": [active_utility_id],
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "CONFIRMED"

        # VERIFICO CHE SU UTILITY NODE L' UTILITY BOOKING RISULTI CONFERMATO
        ub = httpx.get(f"{UTILITY_URL}/utility-bookings/by-field-booking/{data['id']}")
        assert ub.status_code == 200
        bookings = ub.json()
        assert len(bookings) == 1
        assert bookings[0]["status"] == "CONFIRMED"


    # SE UTILITY INESISTENTE -> VOTANO NO -> ABORTED -> ERRORE 409
    def test_2pc_rollback_on_nonexistent_utility(self, active_field_id):
        start, end = _slot(1)
        r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
            "field_id": active_field_id,
            "user_id": "user_e2e_2",
            "start_time": start,
            "end_time": end,
            "utility_ids": [99999],  # ID INESISTENTE
        })
        assert r.status_code == 409
        assert "aborted" in r.json()["detail"].lower()

        # VERIFICO CHE NON ESISTA NESSUN BOOKING CONFIRMED PER QUESTO SLOT
        bookings = httpx.get(f"{FIELD_URL}/bookings").json()
        confirmed_in_slot = [
            b for b in bookings
            if b["field_id"] == active_field_id
               and b["start_time"] == start
               and b["status"] == "CONFIRMED"
        ]
        assert len(confirmed_in_slot) == 0

    # LO STESSO SLOT VIENE PRENOTATO 2 VOLTE -> LA SECONDA RICEVE ERRORE 409
    def test_2pc_slot_locked_on_double_booking(self, active_field_id, active_utility_id):
        start, end = _slot(2)
        payload = {
            "field_id": active_field_id,
            "user_id": "user_e2e_3",
            "start_time": start,
            "end_time": end,
            "utility_ids": [active_utility_id],
        }

        r1 = httpx.post(f"{FIELD_URL}/bookings/2pc", json=payload)
        r2 = httpx.post(f"{FIELD_URL}/bookings/2pc", json=payload)
        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [201, 409]

    # SENZA UTILITY_IDS, IL PREPARE È VUOTO -> COMMITTED
    def test_2pc_no_utilities_still_commits(self, active_field_id):
        start, end = _slot(3)
        r = httpx.post(f"{FIELD_URL}/bookings/2pc", json={
            "field_id": active_field_id,
            "user_id": "user_e2e_4",
            "start_time": start,
            "end_time": end,
            "utility_ids": [],  # ID VUOTO
        })

        assert r.status_code == 201
        assert r.json()["status"] == "CONFIRMED"

