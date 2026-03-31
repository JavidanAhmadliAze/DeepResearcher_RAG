import asyncio
import pytest

from src.db.database import engine, init_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all DB tables once before the test session starts.

    Uses a plain asyncio.run() so the setup has its own short-lived event
    loop that is fully torn down before anyio spins up per-test loops.
    engine.dispose() flushes the pool so tests always open fresh connections
    in their own event loops — prevents the "Future attached to a different
    loop" / "operation in progress" cascade errors.
    """

    async def _setup():
        await init_db()
        await engine.dispose()

    asyncio.run(_setup())
