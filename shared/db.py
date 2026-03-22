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

class Base(DeclarativeBase):
    """Base class for all ORM models in the project."""
    pass

class DatabaseSessionManager:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def init(self) -> None:
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

        self._session_factory = async_sessionmaker(
            bind = self._engine,
            class_ = AsyncSession,
            expire_on_commit = False,
            autoflush = False,
        )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_factory is None:
            raise RuntimeError("Call .init() before using db.")
        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

db_manager = DatabaseSessionManager()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session
