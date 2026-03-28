import asyncio
import httpx

FIELD_NODE_URL = "http://localhost:8001"
N_CONCURRENT = 10  # NUMERO DI  RICHIESTE CHE MANDERO' COME TEST

async def create_test_field(client: httpx.AsyncClient) -> int:   # CREO UN CAMPO DI TEST
    response = await client.post(
        f"{FIELD_NODE_URL}/fields",
        json={
            "name": "Test Concurrency Field",
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
async def try_book(client: httpx.AsyncClient, field_id: int, user_id: str) -> dict:
    payload = {
        "field_id": field_id,
        "user_id": user_id,
        "start_time": "2026-03-28T10:00:00",
        "end_time": "2026-03-28T11:00:00",
    }
    response = await client.post(
        f"{FIELD_NODE_URL}/bookings",
        json=payload,
        timeout=10.0,
    )
    return {
        "user_id": user_id,
        "status_code": response.status_code,
        "body": response.json(),
    }

async def run_test():
    print(f"Launching {N_CONCURRENT} concurrent requests on the same slot...\n") # LANCIO LE 10 RICHIESTE

    async with httpx.AsyncClient() as client:
        field_id = await create_test_field(client)
        tasks = [try_book(client, field_id, f"user_{i}") for i in range(N_CONCURRENT)]
        results = await asyncio.gather(*tasks)

    # CLASSIFICO I RISULTATI PER STATUS CODE
    successes = [r for r in results if r["status_code"] == 201]
    conflicts = [r for r in results if r["status_code"] == 409]
    errors = [r for r in results if r["status_code"] not in (201,409)]

    print(f"Bookings created (201): {len(successes)}")
    print(f"Conflicts occurred (409): {len(conflicts)}")
    print(f"Unexpected errors: {len(errors)}")

    if errors:  # GESTIONE ERRORI
        print("\n Unexpected errors details:")
        for e in errors:
            print(f"    -> {e['user_id']} | {e['status_code']} | {e['body']} ")

    assert len(errors) == 0, \
        f"FAIL: {len(errors)} responses with unexpected status code."

    assert len(successes) == 1, \
        f"FAIL: expected 1 booking, obtained {len(successes)}. Distributed lock not working!"

    assert len(conflicts) == N_CONCURRENT-1, \
        f"FAIL: expected {N_CONCURRENT-1} conflicts, obtained {len(conflicts)}."

    winner = successes[0]    # PRENDO CHI E' RIUSCITO A PRENOTARE IL CAMPO E I SUOI DATI
    print(f"WINNER: {winner['user_id']} successfully booked a field")
    print(f"    Booking ID: {winner['body'].get('id')}")
    print(f"    Status: {winner['body'].get('status')}")
    print("TEST PASSED")

if __name__ == "__main__":
    asyncio.run(run_test())
