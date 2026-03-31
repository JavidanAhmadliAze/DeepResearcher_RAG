from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.security import get_current_user
from src.db.database import get_db
from src.db.models import User
from src.db.repositories import ChatRepository

router = APIRouter(tags=["history"])


@router.get("/threads")
async def list_threads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ChatRepository(db)
    messages = await repo.get_user_thread_starters(current_user.id)

    threads: dict[str, dict] = {}
    for msg in messages:
        if msg.thread_id not in threads:
            threads[msg.thread_id] = {
                "thread_id": msg.thread_id,
                "title": msg.content[:80],
                "created_at": msg.created_at,
            }

    return sorted(threads.values(), key=lambda t: t["created_at"], reverse=True)


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ChatRepository(db)
    deleted = await repo.delete_thread(thread_id, current_user.id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Thread not found")


@router.get("/history/{thread_id}")
async def get_history(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = ChatRepository(db)
    messages = await repo.get_thread_messages(thread_id, current_user.id)
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages]
