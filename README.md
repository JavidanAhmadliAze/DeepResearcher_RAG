# Deep Research Assistant

An AI-powered research system built with a multi-agent architecture that conducts deep, multi-step research and delivers comprehensive reports. Users submit queries through a web UI or REST API, and a hierarchical agent workflow orchestrates research using specialized agents, web search, and LLMs to produce detailed findings with cited sources.

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [AI Engineering](#ai-engineering)
  - [Agent Orchestration](#agent-orchestration)
  - [LLMOps with Langfuse](#llmops-with-langfuse)
  - [Memory Persistence](#memory-persistence)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Manual Setup](#manual-setup)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [CI/CD Pipeline](#cicd-pipeline)

---

## Features

- Multi-agent research workflow with scope analysis, planning, parallel execution, and synthesis
- Real-time streaming of workflow progress and final report via Server-Sent Events (SSE)
- Thread-based conversation history with persistent agent state across sessions
- JWT authentication with per-user message storage
- Full observability with Langfuse tracing (token usage, latency, tool calls per agent)
- Production-ready deployment on Azure App Service with GitHub Actions CI/CD

---

## Architecture Overview

```
User Request (HTTP)
       │
       ▼
  FastAPI Backend
       │
       ▼
  Scope Agent ──► Clarify or Write Research Brief
       │
       ▼
  Supervisor Agent ──► Plan research topics
       │
       ├──► Research Agent 1 (async)
       ├──► Research Agent 2 (async)   ◄── Parallel via asyncio.gather
       └──► Research Agent 3 (async)
       │
       ▼
  Final Report Generator ──► Streams response via SSE
       │
       ▼
  PostgreSQL (Chat History + LangGraph Checkpoints)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI (async) |
| Agent Orchestration | LangGraph 0.2+ |
| LLMs | DeepSeek (`deepseek-chat`, `deepseek-reasoner`) |
| Web Search | Tavily API |
| LLMOps / Observability | Langfuse 2.0+ |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Agent State Checkpointing | LangGraph AsyncPostgresSaver |
| Auth | JWT (python-jose) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | Next.js 14, Tailwind CSS |
| Containerization | Docker, Docker Compose |
| Deployment | Azure App Service |
| Package Manager | `uv` (Python), `npm` (Node) |

---

## AI Engineering

### Agent Orchestration

The system uses a **hierarchical multi-agent architecture** built on LangGraph. The graph is compiled once at startup with a persistent PostgreSQL checkpointer and invoked per user thread, enabling stateful multi-turn conversations.

#### Agent Hierarchy

```
1. Scope Agent
   ├── clarify_with_user  → asks follow-up questions if the query is ambiguous
   └── write_research_brief → transforms the conversation into a structured research brief

2. Supervisor Agent
   ├── Decides which topics to research (up to 6 decision iterations)
   ├── Spawns up to 3 parallel Research Agents via ConductResearch tool
   ├── Uses think_tool for internal chain-of-thought reasoning
   └── Uses retrieve_data_with_score for RAG over prior findings

3. Research Agent (per topic, spawned by Supervisor)
   ├── Runs tavily_search + think_tool in an iterative loop (max 6 iterations)
   └── Compresses findings into a structured ResearchOutput

4. Final Report Generator
   ├── Synthesizes all research notes using deepseek-reasoner
   └── Streams final output character-by-character via SSE
```

#### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Async-first** | `asyncio.gather` runs multiple Research Agents in parallel — concurrent topic research without blocking |
| **Budget control** | Supervisor iteration limit (6) + per-agent iteration limit (6) prevent runaway costs and infinite loops |
| **Command-based routing** | LangGraph `Command` objects route between nodes dynamically based on agent decisions, not static edges |
| **Structured outputs** | Pydantic schemas enforce typed agent outputs (scope decisions, research findings, supervisor actions) to prevent hallucinated tool calls |
| **Modular agents** | Each agent (`scope`, `supervisor`, `research`, `final_reporter`) is an independent module — testable and replaceable |
| **Model routing** | `model_config.yaml` maps each agent role to a specific model, temperature, and token budget — decouples orchestration from model selection |
| **YAML prompt templates** | All prompts centralized in `prompt_templates.yaml` and loaded at module init — enables prompt versioning without touching business logic |

#### Workflow Execution

When a user sends a message, the [workflow_executor.py](src/agents/workflow_executor.py) compiles the LangGraph state machine and invokes it:

```python
graph = StateGraph(ResearchState)
graph.add_node("scope", scope_node)
graph.add_node("supervisor", supervisor_node)
graph.add_node("research", research_node)
graph.add_node("final_report", final_report_node)
compiled = graph.compile(checkpointer=postgres_checkpointer)

# Each user thread resumes from its persisted checkpoint
async for event in compiled.astream(
    {"messages": [user_message]},
    config={"configurable": {"thread_id": thread_id}}
):
    yield format_sse_event(event)
```

---

### LLMOps with Langfuse

[Langfuse](https://langfuse.com) provides full observability over every LLM call in the system without modifying agent logic.

#### What is Traced

- Every LLM call across all agents — inputs, outputs, token counts, latency
- Tool invocations — Tavily search queries and results, think_tool chains
- Agent decision paths — which supervisor iteration triggered which research agent
- Full conversation traces grouped by `thread_id`

#### How It Works

Langfuse's `CallbackHandler` is injected into every model in [src/llm/model_wrapper.py](src/llm/model_wrapper.py). It hooks into LangChain's callback system and automatically captures the full execution trace without any agent-level changes:

```python
from langfuse.callback import CallbackHandler

def get_model(role: str):
    callbacks = []
    if langfuse_keys_configured():
        callbacks.append(CallbackHandler())
    return ChatOpenAI(..., callbacks=callbacks)
```

Langfuse is **fully optional** — if the environment variables are absent, the system runs without tracing and raises no errors.

#### What You Can Monitor

- Token consumption broken down by agent, model, and session
- End-to-end latency per phase (scope → supervisor → research → synthesis)
- Full prompt/completion pairs for debugging agent behavior
- Parallel research agent traces showing which topics were investigated and in what order

#### Configuration

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

---

### Memory Persistence

The system uses a **two-layer persistence model** separating user-facing chat history from internal agent state.

#### Layer 1 — Chat History (PostgreSQL ORM)

User messages and assistant responses are stored in a `chat_history` table, written by [ChatRepository](src/db/repositories/chat_repository.py) after each workflow completion.

```
users        → id, username, email, hashed_password
chat_history → id, user_id (FK), thread_id, role, content, created_at
```

- Retrieved on `GET /history/{thread_id}` for UI rendering
- Supports multiple named threads per user (sidebar thread list)

#### Layer 2 — Agent State Checkpointing (LangGraph AsyncPostgresSaver)

LangGraph's `AsyncPostgresSaver` persists the full agent graph state to PostgreSQL after each node execution. This is distinct from chat history — it stores internal agent state: message accumulations, research notes, scope decisions, and iteration counters.

```python
# src/db/database.py
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def init_checkpointer():
    checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    await checkpointer.setup()   # creates checkpoint tables if not present
    return checkpointer
```

When a user sends a follow-up message, LangGraph automatically restores the prior graph state from the checkpoint for that `thread_id`. The new message is appended and the workflow resumes with full context — no prior research is re-run. The `add_messages` reducer prevents duplicate message accumulation.

#### Summary

| What | Where | When |
|---|---|---|
| User messages & assistant responses | PostgreSQL `chat_history` table | After workflow completes |
| Agent graph state (full internal state) | PostgreSQL via LangGraph AsyncPostgresSaver | After each graph node |
| Auth tokens | JWT (stateless) | Per request |

---

## Project Structure

```
DeepResearchAssistant/
├── src/
│   ├── api/
│   │   ├── main.py                  # FastAPI app, lifespan, CORS, middleware
│   │   ├── routers/
│   │   │   ├── auth.py              # /register, /login
│   │   │   ├── chat.py              # /chat (SSE stream)
│   │   │   ├── history.py           # /history, /threads
│   │   │   └── health.py            # /health
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── security.py              # JWT creation & verification
│   │   └── streaming.py             # SSE event formatting, status messages
│   ├── agents/
│   │   ├── supervisor_agent.py      # Supervisor node, tool dispatch, iteration control
│   │   ├── research_agent.py        # Per-topic research loop, search, compress findings
│   │   ├── scope_agent.py           # clarify_with_user & write_research_brief nodes
│   │   └── workflow_executor.py     # LangGraph graph compilation, final report generation
│   ├── agent_interface/
│   │   ├── states.py                # LangGraph TypedDict state classes
│   │   ├── tools.py                 # ConductResearch, ResearchComplete tool definitions
│   │   └── schemas.py               # Pydantic schemas for structured LLM outputs
│   ├── llm/
│   │   └── model_wrapper.py         # Model factory, Langfuse callback injection
│   ├── db/
│   │   ├── database.py              # SQLAlchemy engine, async session, checkpointer init
│   │   ├── models.py                # User, ChatMessage ORM models
│   │   └── repositories/
│   │       ├── chat_repository.py   # Chat history read/write
│   │       └── user_repository.py   # User lookup and creation
│   ├── config/
│   │   ├── model_config.yaml        # Agent → model routing, temperatures, token budgets
│   │   └── prompt_templates.yaml    # All agent system prompts
│   ├── utils/
│   │   └── tools.py                 # tavily_search, think_tool, summarize_webpage
│   ├── data_retriever/
│   │   └── output_retriever.py      # retrieve_data_with_score (RAG over prior findings)
│   └── frontend/                    # Next.js 14 app
│       ├── app/
│       │   ├── page.tsx             # Main chat UI
│       │   └── components/          # Message, Sidebar, AuthModal, SourceCard
│       └── package.json
├── tests/
│   ├── unit/
│   └── integration/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .github/workflows/
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- A [DeepSeek API key](https://platform.deepseek.com)
- A [Tavily API key](https://tavily.com)
- (Optional) A [Langfuse](https://langfuse.com) account for tracing

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

```bash
# Required
DEEPSEEK_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/research_db
AUTH_SECRET_KEY=your-32-character-minimum-secret-key

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional — LLMOps tracing (Langfuse)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

### Running with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

### Manual Setup

**Backend**

```bash
# Install uv
pip install uv

# Install dependencies
uv sync

# Run the server (database tables created automatically on startup)
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**

```bash
cd src/frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
# Runs on http://localhost:3000
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/register` | Register a new user |
| `POST` | `/login` | Login, returns JWT access token |

### Research

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Start or continue a research thread (SSE stream) |

**Request body:**
```json
{
  "message": "What are the latest advancements in fusion energy?",
  "thread_id": "unique-thread-uuid"
}
```

**SSE Event Types:**

| Event | Description |
|---|---|
| `status` | Workflow phase updates (scope check, planning, researching, synthesizing) |
| `scope_message` | Clarification question from the Scope Agent |
| `background_message` | Tool execution details (search queries, intermediate findings) |
| `content` | Final report delta chunks (streamed character-by-character) |
| `error` | Workflow failure with error message |
| `done` | Stream complete |

### History

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/history/{thread_id}` | Retrieve full conversation for a thread |
| `GET` | `/threads` | List all threads for the authenticated user |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |

> All `/chat`, `/history`, and `/threads` endpoints require `Authorization: Bearer <token>`.

---

## Deployment

The project deploys to **Azure App Service** with separate services for the backend and frontend.

### Backend (Python 3.12)

- Azure App Service with Linux + Python 3.12 runtime
- Environment variables configured in App Service Configuration panel
- PostgreSQL connection string uses `sslmode=require` for Azure-managed databases
- Health check endpoint configured for automatic restarts

### Frontend (Node.js 20)

- Next.js static export built during CI with `NEXT_PUBLIC_API_URL` injected at build time
- Served via `serve` on a Node.js Azure App Service
- Independent App Service from the backend for separate scaling

---

## CI/CD Pipeline

GitHub Actions workflows run on every push to `main`:

1. **Test** — unit and integration tests against a PostgreSQL service container
2. **Build backend** — Docker image build validation
3. **Deploy backend** — Azure App Service deployment via publish profile secret
4. **Build frontend** — `npm run build` with production environment variables
5. **Deploy frontend** — Azure App Service deployment

**Required GitHub Secrets:**

```
AZURE_WEBAPP_PUBLISH_PROFILE      # Backend App Service publish profile
AZURE_FRONTEND_PUBLISH_PROFILE    # Frontend App Service publish profile
NEXT_PUBLIC_API_URL               # Production API URL for frontend build
```
