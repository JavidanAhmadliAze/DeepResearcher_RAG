from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import Literal
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, get_buffer_string
from dotenv import load_dotenv
from src.agent_interface.states import AgentInputState, AgentOutputState
from src.agent_interface.schemas import ClarifyWithUser, ResearchQuestion
from src.llm.model_wrapper import create_model, ainvoke_structured
from src.prompt_engineering.templates import get_prompt
from src.utils.tools import get_today_str
from threading import Lock

load_dotenv()

clarification_instructions = get_prompt("scope_agent","clarification_instructions")
transform_messages_into_research_topic_prompt = get_prompt("scope_agent","transform_messages_into_research_topic_prompt")

_model = None
_model_lock = Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = create_model("scope_agent")
    return _model

async def clarify_with_user(state: AgentInputState) -> Command[Literal["write_research_brief", "__end__"]]:
    result = await ainvoke_structured(_get_model(), ClarifyWithUser, [
        HumanMessage(content=clarification_instructions.format(
            messages = get_buffer_string(messages=state.get("messages", [])),
            date = get_today_str(),
            ))
        ])

    if result.need_clarification:
        return Command(
                goto="__end__",
                update={
                    "messages": [AIMessage(content=result.question)],
                    "needs_clarification": True,
                    "clarification_question": result.question,
                }
            )

    else:
        return Command(
            goto="write_research_brief",
            update={
                "messages": [AIMessage(content=result.verification)],
                "needs_clarification": False,
                "clarification_question": None,
            }
        )

async def write_research_brief(state: AgentOutputState):
    result = await ainvoke_structured(_get_model(), ResearchQuestion, [
        HumanMessage(content=transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(messages=state.get("messages",[])),
            date=get_today_str()
        ))])

    return {"research_brief": result.research_brief,
            "supervisor_messages": [HumanMessage(content=f"{result.research_brief}.")]}

scope_graph = StateGraph(AgentInputState,output_schema=AgentOutputState)

scope_graph.add_node("clarify_with_user", clarify_with_user)
scope_graph.add_node("write_research_brief", write_research_brief)

scope_graph.add_edge(START,"clarify_with_user")
scope_graph.add_edge("write_research_brief", END)

scope_agent = scope_graph.compile()
