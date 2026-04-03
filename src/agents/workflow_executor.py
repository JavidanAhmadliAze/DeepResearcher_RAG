from src.agent_interface.states import AgentInputState, AgentOutputState, SupervisorState
from src.utils.tools import get_today_str
from langchain_core.messages import HumanMessage, AIMessage
from src.llm.model_wrapper import create_model
from src.prompt_engineering.templates import get_prompt
from src.agents.supervisor_agent import supervisor, supervisor_tools, supervisor_agent
from src.agents.scope_agent import scope_agent
from src.agents.guardrail_agent import run_guardrail
from langgraph.graph import StateGraph, START, END
from threading import Lock

final_report_generation_prompt = get_prompt("final_reporter", "final_report_generation_prompt")

_model = None
_model_lock = Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = create_model("final_reporter")
    return _model

async def final_report_generation(state: AgentOutputState):
    """
    Final report generation node.
    Synthesizes all research findings into a comprehensive final report
    and keeps the conversation labeled correctly.
    """
    # Retrieve previous notes and research brief
    notes = state.get("notes", [])
    raw_notes = state.get("raw_notes", [])

    raw_findings = "\n".join(raw_notes)
    findings = "\n".join(notes)
    research_brief = state.get("research_brief", "")

    # Build the final report prompt
    final_report_prompt = final_report_generation_prompt.format(
        research_brief=research_brief,
        findings=findings,
        date=get_today_str()
    )

    # Call the model
    final_report_response = await _get_model().ainvoke([HumanMessage(content=final_report_prompt)])

    # Wrap final report in AIMessage to keep it labeled correctly
    ai_message = AIMessage(content=final_report_response.content)

    # Append to existing messages in state for memory continuity
    previous_messages = state.get("messages", [])
    updated_messages = previous_messages + [ai_message]

    return {
        "final_report": final_report_response.content,
        "messages": updated_messages,  # keep conversation history
    }


async def guardrail_node(state: AgentOutputState) -> dict:
    decision = await run_guardrail(state)
    if not decision.is_safe:
        return {
            "messages": [AIMessage(content=decision.rejection_message)],
            "needs_clarification": True,
            "clarification_question": decision.rejection_message,
            "workflow_error": "guardrail_rejected",
        }
    return {}


def route_after_guardrail(state: AgentOutputState) -> str:
    if state.get("workflow_error") == "guardrail_rejected":
        return END
    return "scope_agent"


def route_after_scope(state: AgentOutputState) -> str:
    if state.get("needs_clarification"):
        return END
    return "supervisor_subgraph"


def route_after_supervisor(state: AgentOutputState) -> str:
    if state.get("workflow_error"):
        return END
    return "final_report_generation"

deep_researcher_builder = StateGraph(AgentOutputState)

deep_researcher_builder.add_node("guardrail", guardrail_node)
deep_researcher_builder.add_node("scope_agent", scope_agent)
deep_researcher_builder.add_node("supervisor_subgraph", supervisor_agent)
deep_researcher_builder.add_node("final_report_generation", final_report_generation)

deep_researcher_builder.add_edge(START, "guardrail")
deep_researcher_builder.add_conditional_edges("guardrail", route_after_guardrail)
deep_researcher_builder.add_conditional_edges("scope_agent", route_after_scope)
deep_researcher_builder.add_conditional_edges("supervisor_subgraph", route_after_supervisor)
deep_researcher_builder.add_edge("final_report_generation", END)



def compile_deep_researcher(checkpointer=None):
    return deep_researcher_builder.compile(checkpointer=checkpointer)


deep_researcher_agent = compile_deep_researcher()
