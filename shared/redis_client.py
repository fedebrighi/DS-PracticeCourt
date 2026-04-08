from __future__ import annotations
from typing import Optional
from redis.asyncio import ConnectionPool, Redis
from shared.config import get_settings

class RedisClientManager:
    def __init__(self) -> None:
        self._pool: Optional[ConnectionPool] = None

    def init(self) -> None:
        settings = get_settings()
        self._pool = ConnectionPool.from_url( # CREO UN UNICO CONNECTION POOL, TUTTE LE RICHIESTE PESCHERANNO DA QUESTO
            settings.redis_url,
            max_connections = 20,
            socket_timeout = 5.0,
            socket_connect_timeout = 5.0,
            retry_on_timeout = True,
            health_check_interval = 30,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.disconnect() # CHIUDE TUTTE LE CONNESSIONI APERTE NEL CONNECTION POOL
            self._pool = None

    def get_client(self) -> Redis:
        if self._pool is None:
            raise RuntimeError("Call .init() before using Redis!")
        return Redis(connection_pool=self._pool, decode_responses=True) # OGNI CHIAMATA CREA UN CLIENT CHE CONDIVIDE IL POOL

    # NON USA IL POOL CONDIVISO PERCHE IL PUB/SUB BLOCCA
    def create_pubsub_client(self) -> Redis:
        if self._pool is None:
            raise RuntimeError("Call .init() before using Redis!")
        settings = get_settings()
        return Redis.from_url(settings.redis_url, decode_responses=True)

redis_manager = RedisClientManager()

async def get_redis() -> Redis:
    return redis_manager.get_client() # USATA DA OGNI ENDPOINT CHE USA REDIS