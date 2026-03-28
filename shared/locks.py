import uuid
from typing import Optional
from redis.asyncio import Redis

# SCRIPT LUA PER IL RELEASE ATOMICO, CONTROLLA TOKEN E CANCELLA SOLO SE E' IL PROPRIETARIO
# KEYS[1] E' LA KEY, ARGV[1] è IL TOKEN DEL RICHIEDENTE, DEL CANCELLA LA CHIAVE LOCK
_LUA_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

class DistributedLock:

    def __init__(self, client: Redis) -> None:
        self._client = client

    # COSTRUISCE LA KEY[1] CHE SARA' USATA NELLO SCRIPT RELASE
    @staticmethod
    def _build_key(key:str) -> str:
        return f"lock:{key}"

    # TENTA DI ACQUISIRE IL LOCK SULLA RISORSA KEY
    async def acquire(self, key:str, ttl_ms: int) -> Optional[str]:
        token = str(uuid.uuid4())  # UUID4 GENERATO ALL'ACQUISIZIONE
        result = await self._client.set(
            self._build_key(key),
            token,
            nx=True, # SET SOLO SE NON ESISTE -> MI GARANTISCE MUTUA ESLUSIONE
            px=ttl_ms, # SCADENZA IN MS -> EVITA DEADLOCK IN CASO DI CRASH
        )
        return token if result else None # RITORNA IL TOKEN SE IL LOCK è ACQUISITO

    # RILASCIA IL LOCK SOLO SE IL TOKEN CORRISPONDE AL PROPRIETARIO CORRENTE
    async def release(self, key:str, token:str) -> bool:
        result = await self._client.eval(
            _LUA_RELEASE_SCRIPT, # CANCELLA LA KEY DEL LOCK SOLO SE è IL TOKEN DEL RICHIEDENTE
            1, # LO SCRIPT USA UNA CHIAVE
            self._build_key(key), # COSTRUISCE QUELLA CHE E' LA KEY[1] NELLO SCRIPT
            token, # ARGV[1] NELLO SCRIPT
        )
        return bool(result)