import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import auth_router, chat_router, health_router, history_router
from src.db.database import init_db

logging.getLogger("opentelemetry.sdk.trace").setLevel(logging.ERROR)

app = FastAPI(title="Deep Research Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.on_event("shutdown")
async def shutdown_event():
    return None

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
