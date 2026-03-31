import traceback
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.workflow_executor import deep_researcher_agent
from src.llm.model_wrapper import get_langfuse_callback
from src.api.schemas import ChatRequest
from src.api.security import get_current_user
from src.api.streaming import (
    FINAL_REPORT_NODE,
    NODE_STATUS_MESSAGES,
    SCOPE_MESSAGE_NODES,
    coerce_text,
    extract_last_ai_content,
    extract_tavily_messages,
    extract_ui_messages,
    format_sse,
    normalize_message_payload,
    normalize_stream_part,
    resolve_node_name,
)
from src.db.database import async_session, get_db
from src.db.models import User
from src.db.repositories import ChatRepository

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_endpoint(
    chat_request: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not chat_request.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")

    repo = ChatRepository(db)
    await repo.save_message(
        user_id=current_user.id,
        role="user",
        content=chat_request.message,
        thread_id=chat_request.thread_id,
    )

    thread_history = await repo.get_thread_messages(chat_request.thread_id, current_user.id)

    input_messages = [
        HumanMessage(content=msg.content) if msg.role == "user" else AIMessage(content=msg.content)
        for msg in thread_history
    ]

    async def stream_response() -> AsyncGenerator[str, None]:
        config = {"configurable": {"thread_id": chat_request.thread_id}}
        inputs = {"messages": input_messages}
        status_message = None
        streamed_chunks: list[str] = []
        fallback_ai_content = None
        emitted_scope_messages: set[str] = set()
        emitted_background_messages: set[str] = set()
        awaiting_clarification = False
        workflow_error = None

        try:
            yield format_sse("status", {"message": "Starting the research workflow"})

            langfuse_cb = get_langfuse_callback()
            if langfuse_cb:
                config["callbacks"] = [langfuse_cb]

            async for part in deep_researcher_agent.astream(
                inputs,
                config=config,
                subgraphs=True,
                stream_mode=["updates", "messages"],
                version="v2",
            ):
                if await request.is_disconnected():
                    return

                stream_type, stream_payload, namespace = normalize_stream_part(part)

                if stream_type == "updates" and isinstance(stream_payload, dict):
                    for node_name, update in stream_payload.items():
                        current_node = resolve_node_name(namespace, node_name)
                        next_status = NODE_STATUS_MESSAGES.get(current_node)
                        if next_status and next_status != status_message:
                            status_message = next_status
                            yield format_sse(
                                "status",
                                {"node": current_node, "message": next_status},
                            )

                        update_error = update.get("workflow_error")
                        if isinstance(update_error, str) and update_error.strip():
                            workflow_error = update_error

                        for ui_message in extract_ui_messages(update):
                            if ui_message in emitted_background_messages:
                                continue
                            emitted_background_messages.add(ui_message)
                            yield format_sse(
                                "background_message",
                                {"node": current_node, "content": ui_message},
                            )

                        for tavily_message in extract_tavily_messages(update):
                            if tavily_message in emitted_background_messages:
                                continue
                            emitted_background_messages.add(tavily_message)
                            yield format_sse(
                                "background_message",
                                {"node": current_node, "content": tavily_message},
                            )

                        content = extract_last_ai_content(update)
                        if content:
                            fallback_ai_content = content
                            if current_node in SCOPE_MESSAGE_NODES and content not in emitted_scope_messages:
                                emitted_scope_messages.add(content)
                                if (
                                    current_node == "clarify_with_user"
                                    and update.get("needs_clarification") is True
                                ):
                                    awaiting_clarification = True
                                yield format_sse(
                                    "scope_message",
                                    {"node": current_node, "content": content},
                                )

                elif stream_type == "messages":
                    message_chunk, metadata = normalize_message_payload(stream_payload)
                    node_name = resolve_node_name(
                        namespace,
                        metadata.get("langgraph_node") or metadata.get("node"),
                    )

                    tool_name = getattr(message_chunk, "name", None)
                    if node_name == "tool_node" and tool_name == "tavily_search":
                        tavily_content = coerce_text(getattr(message_chunk, "content", ""))
                        if tavily_content and tavily_content not in emitted_background_messages:
                            emitted_background_messages.add(tavily_content)
                            yield format_sse(
                                "background_message",
                                {"node": node_name, "content": tavily_content},
                            )
                        continue

                    if node_name != FINAL_REPORT_NODE:
                        continue

                    delta = coerce_text(getattr(message_chunk, "content", ""))
                    if not delta:
                        continue

                    current_text = "".join(streamed_chunks)
                    if current_text and delta.startswith(current_text):
                        delta = delta[len(current_text):]
                    elif current_text.endswith(delta):
                        continue

                    if not delta:
                        continue

                    streamed_chunks.append(delta)
                    yield format_sse("content", {"delta": delta})

            final_content = "".join(streamed_chunks).strip() or fallback_ai_content

            if workflow_error:
                yield format_sse("error", {"message": workflow_error})
                return

            if final_content:
                if not streamed_chunks and final_content not in emitted_scope_messages:
                    yield format_sse("content", {"delta": final_content})

                # Use a fresh session for the final save — the request-scoped session
                # may be exhausted after the long-running stream.
                async with async_session() as save_session:
                    save_repo = ChatRepository(save_session)
                    await save_repo.save_message(
                        user_id=current_user.id,
                        role="assistant",
                        content=final_content,
                        thread_id=chat_request.thread_id,
                    )

            if awaiting_clarification:
                yield format_sse(
                    "status",
                    {
                        "node": "clarify_with_user",
                        "message": "Waiting for your clarification",
                    },
                )

            yield format_sse(
                "done",
                {
                    "thread_id": chat_request.thread_id,
                    "awaiting_clarification": awaiting_clarification,
                },
            )
        except Exception as exc:
            traceback.print_exc()
            yield format_sse(
                "error",
                {"message": str(exc) or "The research workflow failed before a response could finish streaming."},
            )

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
