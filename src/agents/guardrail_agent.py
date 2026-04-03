from threading import Lock

from langchain_core.messages import HumanMessage

from src.agent_interface.schemas import GuardrailDecision
from src.agent_interface.states import AgentInputState
from src.llm.model_wrapper import ainvoke_structured, create_model
from src.prompt_engineering.templates import get_prompt

guardrail_prompt = get_prompt("guardrail_agent", "guardrail_prompt")

_model = None
_model_lock = Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = create_model("guardrail_agent")
    return _model


async def run_guardrail(state: AgentInputState) -> GuardrailDecision:
    """Evaluate the latest user message for prompt injection and unwanted requests.

    Returns a GuardrailDecision indicating whether the input is safe,
    and a rejection message to surface to the user if not.
    """
    messages = state.get("messages", [])
    # Only inspect the latest human message
    user_message = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human" or msg.__class__.__name__ == "HumanMessage":
            user_message = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    return await ainvoke_structured(
        _get_model(),
        GuardrailDecision,
        [HumanMessage(content=guardrail_prompt.format(user_message=user_message))],
    )
