from unittest.mock import MagicMock, AsyncMock
import httpx
import pytest
from unittest.mock import patch
from two_pc_coordinator import prepare_all, commit_all, rollback_all

UTILITY_URL = "http://fake-utility:8002"

# COSTRUISCO IL MOCK DI UNA RISPOSTA HTTP, SIMILE A QUELLA RESTITUITA DA UTILITY_NODE
def _mock_http_response(json_body: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()
    return mock_resp

# COSTRUISCO IL MOCK DI UN CLIENT REDIS, PER VERIFICARE CHIAMATE CORRETTE DI _set_txn_state
def _mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock()
    return redis

@pytest.mark.asyncio
async def test_prepare_all_all_yes():
    # TUTTE LE UTILITIES VOTANO YES
    redis = _mock_redis()
    yes_response = _mock_http_response({"vote":"yes", "utility_booking_id": 42})
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value = yes_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        ok, ids = await prepare_all(UTILITY_URL, redis, field_booking_id = 1, utility_ids=[10,11])

    assert ok is True
    assert ids == [42, 42]
    # VERIFICO LA SEQUENZA DI STATI SCRITTI IN REDIS DURANTE L'ESECUZIONE
    calls = [call.args[1] for call in redis.set.await_args_list]
    assert any('"init"' in c for c in calls) # PRIMA DEVE RICEVERE INIT
    assert any('"prepared"' in c for c in calls) # POI PREPARED

@pytest.mark.asyncio
async def test_prepare_all_one_no():
    # PRIMA UTILITY VOTA YES E LA SECONDA VOTA NO
    redis = _mock_redis()
    yes_resp = _mock_http_response({"vote":"yes", "utility_booking_id": 7}) # PASSA SOLO L'ID DEL PRIMO
    no_resp = _mock_http_response({"vote":"no", "utility_booking_id": None, "reason":"inactive"})
    responses = [yes_resp, no_resp]
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect = responses)
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        ok, ids = await prepare_all(UTILITY_URL, redis, field_booking_id = 2, utility_ids=[10,11])

    assert ok is False
    assert ids == [7]

@pytest.mark.asyncio
async def test_prepare_all_timeout():
    # UTILITY NODE NON RISPONDE ENTRO IL TIMEOUT
    redis = _mock_redis()
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect = httpx.TimeoutException("timeout"))
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        ok, ids = await prepare_all(UTILITY_URL, redis, field_booking_id = 3, utility_ids=[10])

    assert ok is False
    assert ids == []

@pytest.mark.asyncio
async def test_prepare_all_no_utilities():
    # NESSUNA UTILITY RICHIESTA
    redis = _mock_redis()
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value = AsyncMock())
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        ok, ids = await prepare_all(UTILITY_URL, redis, field_booking_id = 4, utility_ids=[])

    assert ok is True
    assert ids == []

@pytest.mark.asyncio
async def test_commit_all_sets_committed():
    # COMMIT CON IDS VALIDI, SI AGGIORNA LO STATO A COMMITTED
    redis = _mock_redis()
    commit_resp = _mock_http_response({"ok": True})
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value = commit_resp)
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        await commit_all(UTILITY_URL, redis, field_booking_id = 5, utility_booking_ids=[42])

    redis.set.assert_awaited()
    last_call_payload = redis.set.await_args_list[-1].args[1]
    assert '"committed"' in last_call_payload

@pytest.mark.asyncio
async def test_commit_all_empty_ids_still_committed():
    # NESSUNA UTILITY MA REDIS DEVE COMUNQUE RICEVERE COMMITTED
    redis = _mock_redis()
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        await commit_all(UTILITY_URL, redis, field_booking_id = 6, utility_booking_ids=[])
    mock_client.post.assert_not_awaited() # NESSUNA CHIAMATA HTTP QUINDI LISTA VUOTA
    last_call_payload = redis.set.await_args_list[-1].args[1]
    assert '"committed"' in last_call_payload

@pytest.mark.asyncio
async def test_rollback_all_sets_aborted():
    # ROLLBACK CON STATO REDIS AD ABORTED
    redis = _mock_redis()
    rollback_resp = _mock_http_response({"ok": True})
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value = rollback_resp)
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        await rollback_all(UTILITY_URL, redis, field_booking_id = 7, utility_booking_ids=[42])

    last_call_payload = redis.set.await_args_list[-1].args[1]
    assert '"aborted"' in last_call_payload

@pytest.mark.asyncio
async def test_rollback_all_survives_http_failure():
    # UTILITY NODE NON RAGGIUNGIBILE DURANTE IL ROLLACK MA REDIS DEVE COMUNQUE RICEVERE ABORTED
    redis = _mock_redis()
    with patch("field_node.app.two_pc_coordinator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect = httpx.RequestError("network down"))
        MockClient.return_value.__aenter__ = AsyncMock(return_value = mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value = False)
        await rollback_all(UTILITY_URL, redis, field_booking_id = 8, utility_booking_ids=[99])

    last_call_payload = redis.set.await_args_list[-1].args[1]
    assert '"aborted"' in last_call_payload
