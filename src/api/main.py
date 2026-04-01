import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import auth_router, chat_router, health_router, history_router
from src.db.database import init_db, init_checkpointer, close_checkpointer

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
    try:
        await init_db()
    except Exception as e:
        print(f"Database init failed, but starting app anyway: {e}")

    try:
        import src.agents.workflow_executor as _wf
        import src.api.routers.chat as _chat

        checkpointer = await init_checkpointer()
        agent = _wf.compile_deep_researcher(checkpointer)
        # Patch both module bindings so the chat router picks up the new agent.
        _wf.deep_researcher_agent = agent
        _chat.deep_researcher_agent = agent
        print("LangGraph checkpointer initialised — persistent memory enabled.")
    except Exception as e:
        print(f"Checkpointer init failed, running without persistent memory: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    await close_checkpointer()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(history_router)
