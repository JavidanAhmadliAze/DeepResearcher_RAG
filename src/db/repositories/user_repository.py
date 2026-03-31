from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_username_or_email(self, username: str, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(
                or_(User.username == username, User.email == email)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str, normalized_email: str) -> User | None:
        """Look up a user by username or email (supports login with either)."""
        result = await self.db.execute(
            select(User).where(
                or_(User.username == identifier, User.email == normalized_email)
            )
        )
        return result.scalar_one_or_none()

    async def create(self, username: str, email: str, hashed_password: str) -> User:
        user = User(username=username, email=email, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
