from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ChatMessage


class ChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_message(
        self, user_id: int, role: str, content: str, thread_id: str
    ) -> ChatMessage:
        msg = ChatMessage(user_id=user_id, role=role, content=content, thread_id=thread_id)
        self.db.add(msg)
        await self.db.commit()
        return msg

    async def get_thread_messages(self, thread_id: str, user_id: int) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.user_id == user_id,
            )
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return list(result.scalars().all())

    async def get_user_thread_starters(self, user_id: int) -> list[ChatMessage]:
        """Return the first user message of every thread (for thread listing)."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at)
        )
        return list(result.scalars().all())

    async def delete_thread(self, thread_id: str, user_id: int) -> int:
        result = await self.db.execute(
            delete(ChatMessage).where(
                ChatMessage.thread_id == thread_id,
                ChatMessage.user_id == user_id,
            )
        )
        await self.db.commit()
        return result.rowcount
