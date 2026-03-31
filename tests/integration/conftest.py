import asyncio
import os
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import src.db.database as _db
from src.db.models import Base


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables and swap the global engine/session-factory to NullPool.

    NullPool opens a fresh asyncpg connection per operation and closes it
    immediately after — no connection is ever held in a pool between requests,
    so there is no event-loop binding across tests and no
    "another operation is in progress" / "Future attached to different loop"
    errors.
    """
    url = os.environ.get("DATABASE_URL", _db.DATABASE_URL)

    async def _init():
        tmp_engine = create_async_engine(url, poolclass=NullPool)
        async with tmp_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await tmp_engine.dispose()

        # Patch the module globals so every FastAPI request that calls
        # get_db() uses the NullPool engine for the rest of the test session.
        _db.engine = create_async_engine(url, poolclass=NullPool)
        _db.async_session = async_sessionmaker(
            _db.engine, expire_on_commit=False, class_=AsyncSession
        )

    asyncio.run(_init())
