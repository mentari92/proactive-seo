"""Async database lifecycle and tenant transaction context."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class Database:
    """Own the async SQLAlchemy engine and tenant-aware session factory."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(url, echo=echo, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self, org_id: UUID | None = None, user_id: UUID | None = None) -> AsyncIterator[AsyncSession]:
        """Open a transaction and set PostgreSQL RLS context locally."""
        async with self.sessions.begin() as session:
            if org_id is not None:
                await session.execute(
                    text("SELECT set_config('app.current_org_id', :value, true)"),
                    {"value": str(org_id)},
                )
            if user_id is not None:
                await session.execute(
                    text("SELECT set_config('app.current_user_id', :value, true)"),
                    {"value": str(user_id)},
                )
            yield session

    async def close(self) -> None:
        """Dispose pooled connections during service shutdown."""
        await self.engine.dispose()
