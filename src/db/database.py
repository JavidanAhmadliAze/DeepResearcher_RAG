import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Base
from dotenv import load_dotenv

load_dotenv()

# Local docker-compose default; production value comes from the DATABASE_URL env var
# set by Terraform (includes ?ssl=true for Azure PostgreSQL).
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://javidan:password@db:5432/research_db")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        # Import models here to ensure they are registered with Base.metadata
        from src.db.models import User, ChatMessage
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session
