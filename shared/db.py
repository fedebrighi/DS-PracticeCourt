from __future__ import annotations
from collections.abc import AsyncGenerator
from typing import Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool
from shared.config import get_settings
from contextlib import asynccontextmanager


class Base(DeclarativeBase):
    """Base class for all ORM models in the project that are going to inherit it"""
    pass

class DatabaseSessionManager:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def init(self) -> None: # CREA LA CONNESSIONE FISICA AL DB E LA SESSION FACTORY, CHIAMATA SOLO UNA VOLTA
        settings = get_settings()
        self._engine = create_async_engine(
            settings.database_url,
            poolclass = AsyncAdaptedQueuePool,
            pool_size = 5,
            max_overflow = 10,
            pool_pre_ping = True,
            pool_recycle = 3600,
            echo = settings.debug,
        )

        self._session_factory = async_sessionmaker( # COLEI CHE PRODUCE LE SESSIONI ( IN CUI POI FACCIO LE OPERAZIONI SUL DB)
            bind = self._engine,
            class_ = AsyncSession,
            expire_on_commit = False,
            autoflush = False,
        )

    async def close(self) -> None:  # CHIUDE TUTTE LE CONNESSIONI AL DB
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]: # PRODUCE UNA SESSIONE PER OGNI RICHIESTA HTTP
        if self._session_factory is None:
            raise RuntimeError("Call .init() before using db.")
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    # CONTEXT MANAGER PER USARE UNA SESSIONE DB FUORI DAL CONTESTO DI UNA REQUEST, USATO DAL RECOVERY JOB
    @asynccontextmanager
    async def session(self):
        if self._session_factory is None:
            raise RuntimeError("Call .init() before using db")
        async with self._session_factory() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

db_manager = DatabaseSessionManager()

async def get_db() -> AsyncGenerator[AsyncSession, None]: # INIETTA UNA SESSIONE DB NEGLI ENDPOINT CHE LA RICHIEDONO
    async for session in db_manager.get_session():
        yield session
