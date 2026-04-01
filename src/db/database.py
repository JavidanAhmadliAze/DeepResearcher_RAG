import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Base
from dotenv import load_dotenv

load_dotenv()

# Local docker-compose default; production value comes from the DATABASE_URL env var
# set by Terraform (includes ?sslmode=require for Azure PostgreSQL).
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://javidan:password@db:5432/research_db")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        from src.db.models import User, ChatMessage
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session


def _psycopg_url() -> str:
    """Convert asyncpg SQLAlchemy URL to a plain psycopg3 connection string."""
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


# Holds the context manager so shutdown can close the connection pool cleanly.
_checkpointer_cm = None


async def init_checkpointer():
    """Open an AsyncPostgresSaver via from_conn_string and create its tables."""
    global _checkpointer_cm
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(_psycopg_url())
    checkpointer = await _checkpointer_cm.__aenter__()
    await checkpointer.setup()
    return checkpointer


async def close_checkpointer():
    """Close the underlying psycopg3 connection pool opened by init_checkpointer."""
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
