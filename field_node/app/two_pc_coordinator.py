import json
import httpx
from redis.asyncio import Redis
from shared.schemas import TwoPCTransactionState, PrepareRequest, PrepareResponse, TwoPCVote, CommitRollbackRequest

_TXN_TTL_S = 300 # TTL DELLO STATO DELLA TRANSIZIONE
_HTTP_TIMEOUT = 5.0 # QUANTO ASPETTA IL COORDINATORE PRIMA DI CONSIDERARE UTILITY NODE IRRAGGIUNGIBILE

# REDIS STATE HELPER
async def _set_txn_state(
        redis: Redis,
        field_booking_id: int,
        state: TwoPCTransactionState,
        utility_booking_ids: list[int],
) -> None:
    key = f"2pc:txn:{field_booking_id}" # INDIRIZZO DENTRO REDIS
    payload = json.dumps({"state": state.value, "utility_booking_ids": utility_booking_ids}) # VALORE SALVATO SULLA KEY
    await redis.set(key, payload, ex =_TXN_TTL_S)

# PREPARE PHASE (1)

async def prepare_all(
        utility_node_url: str,
        redis: Redis,
        field_booking_id: int,
        utility_ids: list[int],
) -> tuple[bool, list[int]]:

    confirmed_ids:list[int] = [] # LISTA CHE ACCUMULA GLI ID DELLE UTILITY BOOKINGS CREATE IN PENDING

    # INIZIO TRANSAZIONE IN REDIS
    await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.INIT, [])

    # APRO UN SINGOLO CLIENT HTTP RIUTILIZZATO PER TUTTE LE CHIAMATE AL PARTECIPANTE
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for utility_id in utility_ids:
            #COSTRUISCO IL PAYLOAD DA MANDARE AL PARTECIPANTE
            req = PrepareRequest(field_booking_id=field_booking_id, utility_id=utility_id)
            try:
                resp = await client.post(
                    f"{utility_node_url}/internal/prepare",
                    json=req.model_dump() # SERIALIZZATO IN JSON
                )
                resp.raise_for_status() # GUARDA LO STATUS PER VEDERE SE DEVE SOLLEVARE UN HTTPStatusError
                vote = PrepareResponse.model_validate(resp.json()) # DESERIALIZZO LA RISPOSTA JSON
                if vote.vote == TwoPCVote.YES and vote.utility_booking_id is not None:
                    confirmed_ids.append(vote.utility_booking_id) # SALVO ID PER USARLO IN COMMIT/ROLLBACK
                else:
                    return False, confirmed_ids
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError):
                return False, confirmed_ids # LA MANCATA RISPOSTA DEL PARTECIPANTE VALE COME UN NO
        # TUTTI I PARTECIPANTIHANNO VOTATO YES QUINDI AGGIORNO LO STATO DELLA TRANSZIONE IN PREPARED
        await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.PREPARED, confirmed_ids)
        return True, confirmed_ids

# COMMIT PHASE (2)

async def commit_all(
        utility_node_url: str,
        redis: Redis,
        field_booking_id: int,
        utility_booking_ids: list[int]
) -> None:
    # CASO IN CUI utility_ids E'VUOTA, AGGIORNO A COMMITTED O STATO REDIS ALTRIMENTI RIMARREBBE
    # BLOCCATO SU PREPARED
    if not utility_booking_ids:
        await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.COMMITTED,[])
        return
    # COSTRUISCO IL PAYLOAD CON TUTTI GLI IDS DELLE UTILITY_BOOKINGS DA CONFERMARE
    req = CommitRollbackRequest(
        field_booking_id = field_booking_id,
        utility_booking_ids = utility_booking_ids,
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{utility_node_url}/internal/commit",
            json=req.model_dump()
        )
        resp.raise_for_status()
    # AGGIORNO LO STATO REDIS SOLO DOPO CHE IL CLIENT HTTP SI È CHIUSO COSI SONO CERTO
    # CHE LA CHIAMATA È COMPLETATA
    await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.COMMITTED, utility_booking_ids)

# ROLLBACK PHASE (2 - PATH DI ERRORE)
async def rollback_all(
        utility_node_url: str,
        redis: Redis,
        field_booking_id: int,
        utility_booking_ids: list[int]
) -> None:
    # CASO SPECIALE IN CUI IL PRIMO PARTECIPANTE HA VOTATO NO PRIMA DI CREARE UNA BOOKING
    # SEGNO COMUNQUE ABORTED IN REDIS ANCHE SE NON CE NULLA DA ANNULLARE
    if not utility_booking_ids:
        await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.ABORTED, [])
        return
    req = CommitRollbackRequest(
        field_booking_id=field_booking_id,
        utility_booking_ids=utility_booking_ids
    )
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            # COSTRUISCO IL PAYLOAD CON GLI IDS DA ANNULLARE
            resp = await client.post(
                f"{utility_node_url}/internal/rollback",
                json = req.model_dump()
            )
            resp.raise_for_status()
        # SE UTIITY NODE NON RISPONDE NON SOLLEVO ECCEZIONI, IL COORDINATORE HA GIA DECISO DI ABORTIRE
        # IL FIELD_BOOKING SARÀ SEGNATO A FAILED QUINDI NESSUNA PRENOTAZIONE RISULTERÀ MAI
        # CONFERMATA PARZIALMENTE
        except httpx.HTTPError:
            pass
    # AGGIORNO LO STATO REDIS AD ABORTED
    await _set_txn_state(redis, field_booking_id, TwoPCTransactionState.ABORTED, utility_booking_ids)