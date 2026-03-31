import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

FINAL_REPORT_NODE = "final_report_generation"
SCOPE_MESSAGE_NODES = {
    "scope_agent",
    "clarify_with_user",
    "write_research_brief",
}
NODE_STATUS_MESSAGES = {
    "scope_agent": "Scoping your request",
    "clarify_with_user": "Checking whether clarification is needed",
    "write_research_brief": "Preparing the research brief",
    "supervisor_subgraph": "Planning the research run",
    "supervisor": "Planning the next research step",
    "supervisor_tools": "Running research tools",
    "llm_call": "Reviewing sources and deciding what to inspect next",
    "tool_node": "Collecting evidence from tools",
    "compress_research": "Condensing the research findings",
    FINAL_REPORT_NODE: "Writing the final response",
}


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
        return "".join(parts)
    return ""


def extract_last_ai_content(payload: Any) -> str | None:
    if isinstance(payload, list):
        for item in reversed(payload):
            if isinstance(item, AIMessage):
                content = coerce_text(item.content)
                if content:
                    return content
            content = extract_last_ai_content(item)
            if content:
                return content

    if isinstance(payload, dict):
        messages = payload.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, AIMessage):
                    content = coerce_text(message.content)
                    if content:
                        return content

        for value in payload.values():
            content = extract_last_ai_content(value)
            if content:
                return content

    return None


def normalize_stream_part(part: Any) -> tuple[str | None, Any, list[str]]:
    if isinstance(part, dict) and "type" in part and "data" in part:
        namespace = part.get("ns") or []
        return part["type"], part["data"], namespace

    if isinstance(part, tuple) and len(part) == 2 and isinstance(part[0], str):
        return part[0], part[1], []

    return None, part, []


def normalize_message_payload(payload: Any) -> tuple[Any, dict[str, Any]]:
    if isinstance(payload, tuple) and len(payload) == 2:
        message_chunk, metadata = payload
        if isinstance(metadata, dict):
            return message_chunk, metadata
        return message_chunk, {}

    return payload, {}


def resolve_node_name(namespace: list[str], fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    if namespace:
        return namespace[-1].split(":")[0]
    return None


def extract_ui_messages(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []

    ui_messages = payload.get("ui_messages")
    if not isinstance(ui_messages, list):
        return []

    return [message for message in ui_messages if isinstance(message, str) and message.strip()]


def extract_tavily_messages(payload: Any) -> list[str]:
    messages: list[str] = []

    if isinstance(payload, ToolMessage):
        if payload.name == "tavily_search":
            content = coerce_text(payload.content)
            if content:
                messages.append(content)
        return messages

    if isinstance(payload, list):
        for item in payload:
            messages.extend(extract_tavily_messages(item))
        return messages

    if isinstance(payload, dict):
        for value in payload.values():
            messages.extend(extract_tavily_messages(value))

    return messages
