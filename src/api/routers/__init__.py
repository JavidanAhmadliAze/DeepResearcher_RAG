from src.api.routers.auth import router as auth_router
from src.api.routers.chat import router as chat_router
from src.api.routers.health import router as health_router
from src.api.routers.history import router as history_router

__all__ = [
    "auth_router",
    "chat_router",
    "health_router",
    "history_router",
]
