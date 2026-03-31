# Deep Research Assistant

Deep research UI and API backed by a LangGraph multi-agent workflow.

## Quick Start
1. Create a `.env` file with `DEEPSEEK_API_KEY` and an async SQLAlchemy database URL such as `postgresql+asyncpg://user:password@localhost:5432/research_db`.
2. Install dependencies with `uv`:
   ```bash
   uv sync
   ```
3. Start the backend:
   ```bash
   uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Serve the frontend from [`src/frontend`](./src/frontend) or run the full stack with Docker Compose:
   ```bash
   docker compose up --build
   ```

## Streaming Behavior
- The FastAPI `/chat` endpoint streams server-sent events.
- The UI renders workflow status updates while the agentic workflow runs.
- Final assistant text is streamed into the active chat message as it is produced.
