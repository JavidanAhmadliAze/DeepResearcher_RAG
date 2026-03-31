import json
import os
from pathlib import Path
from typing import Any, TypeVar
import yaml
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "model_config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    MODEL_CONFIG = yaml.safe_load(f)

StructuredSchemaT = TypeVar("StructuredSchemaT", bound=BaseModel)
MAX_STRUCTURED_OUTPUT_RETRIES = 2

def create_model(agent_name: str) -> ChatOpenAI:
    """
    Creates a standard LangChain ChatOpenAI model based on the agent name.
    """
    routing = MODEL_CONFIG.get("routing", {})
    model_key = routing.get(agent_name, "deepseek-chat")
    
    models_cfg = MODEL_CONFIG.get("models", {})
    cfg = models_cfg.get(model_key, models_cfg.get("deepseek-chat", {}))
    
    callbacks = []
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        callbacks.append(CallbackHandler())
    
    return ChatOpenAI(
        model=cfg.get("model", "deepseek-chat"),
        temperature=cfg.get("temperature", 0.0),
        max_tokens=cfg.get("max_tokens", 8000),
        timeout=cfg.get("timeout", 30),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        streaming=True,
        callbacks=callbacks
    )
    

def get_langfuse_callback() -> CallbackHandler | None:
    """
    Returns a Langfuse CallbackHandler if the public key is set in environment vars.
    """
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        return CallbackHandler()
    return None


def _content_to_text(content: Any) -> str:
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
    return str(content)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain a valid JSON object")

    return stripped[start:end + 1]


def _structured_output_prompt(schema: type[StructuredSchemaT]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    return (
        "Return only a valid JSON object with no markdown or extra commentary. "
        f"Match this schema exactly: {schema_json}"
    )


def _parse_structured_response(
    schema: type[StructuredSchemaT],
    response_content: Any,
) -> StructuredSchemaT:
    text = _content_to_text(response_content)
    json_payload = _extract_json_object(text)
    return schema.model_validate_json(json_payload)


async def ainvoke_structured(
    model: ChatOpenAI,
    schema: type[StructuredSchemaT],
    messages: list[Any],
) -> StructuredSchemaT:
    output_instructions = _structured_output_prompt(schema)
    retry_messages = list(messages)
    last_error: Exception | None = None

    for _ in range(MAX_STRUCTURED_OUTPUT_RETRIES + 1):
        response = await model.ainvoke(
            retry_messages + [HumanMessage(content=output_instructions)]
        )
        try:
            return _parse_structured_response(schema, response.content)
        except Exception as exc:
            last_error = exc
            retry_messages.append(
                HumanMessage(
                    content=(
                        "Your previous response was not valid JSON for the required schema. "
                        f"Validation error: {exc}. "
                        "Return only a corrected JSON object with the exact schema and no markdown."
                    )
                )
            )
            retry_messages.append(
                HumanMessage(
                    content=f"Previous invalid output:\n{_content_to_text(response.content)[:4000]}"
                )
            )

    raise ValueError(f"Failed to parse structured model output after retries: {last_error}")


def invoke_structured(
    model: ChatOpenAI,
    schema: type[StructuredSchemaT],
    messages: list[Any],
) -> StructuredSchemaT:
    output_instructions = _structured_output_prompt(schema)
    retry_messages = list(messages)
    last_error: Exception | None = None

    for _ in range(MAX_STRUCTURED_OUTPUT_RETRIES + 1):
        response = model.invoke(
            retry_messages + [HumanMessage(content=output_instructions)]
        )
        try:
            return _parse_structured_response(schema, response.content)
        except Exception as exc:
            last_error = exc
            retry_messages.append(
                HumanMessage(
                    content=(
                        "Your previous response was not valid JSON for the required schema. "
                        f"Validation error: {exc}. "
                        "Return only a corrected JSON object with the exact schema and no markdown."
                    )
                )
            )
            retry_messages.append(
                HumanMessage(
                    content=f"Previous invalid output:\n{_content_to_text(response.content)[:4000]}"
                )
            )

    raise ValueError(f"Failed to parse structured model output after retries: {last_error}")
