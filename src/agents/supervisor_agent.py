from src.agent_interface.states import SupervisorState
from src.agent_interface.tools import ConductResearch, ResearchComplete
from langchain_core.messages import SystemMessage, ToolMessage, BaseMessage, HumanMessage, filter_messages
from src.utils.tools import get_today_str, think_tool
from langgraph.types import Command
from src.agents.research_agent import research_agent
from src.data_retriever.output_retriever import retrieve_data_with_score
from langgraph.graph import StateGraph, START, END
import asyncio
from threading import Lock
from typing_extensions import Literal
from src.llm.model_wrapper import create_model, get_langfuse_callback
from src.prompt_engineering.templates import get_prompt

# Prompts are safe to load at module level (no NAT dependency)
lead_researcher_prompt = get_prompt("supervisor_agent", "lead_researcher_prompt")

tools = [ConductResearch, ResearchComplete, think_tool, retrieve_data_with_score]

# This prevents infinite loops and controls research depth per topic
max_researcher_iterations = 6  # ConductResearch sub-agent budget

# Maximum number of concurrent research agents the supervisor can launch
max_concurrent_researchers_unit = 3

_model = None
_model_with_tools = None
_model_lock = Lock()


def get_model():
    """Lazily initialize the model and model_with_tools on first call."""
    global _model, _model_with_tools

    if _model is not None and _model_with_tools is not None:
        return _model, _model_with_tools

    with _model_lock:
        if _model is None:
            _model = create_model("supervisor_agent")
        if _model_with_tools is None:
            _model_with_tools = _model.bind_tools(tools)

    if _model is None or _model_with_tools is None:
        raise RuntimeError("Failed to initialize supervisor model bindings")

    return _model, _model_with_tools


def get_notes_from_tool_calls(messages: list[BaseMessage]) -> list[str]:
    """Extract research notes from ToolMessage objects in supervisor message history."""
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]


def finalize_supervisor(state: SupervisorState) -> dict:
    """Build the final supervisor state handed to report generation."""
    return {
        "notes": get_notes_from_tool_calls(state.get("supervisor_messages", [])),
        "research_brief": state.get("research_brief", ""),
        "trigger_search": state.get("trigger_search", False),
        "research_iterations": state.get("research_iterations", 0),
    }


async def supervisor(state: SupervisorState) -> Command[Literal["supervisor_tools"]]:
    """Coordinate research activities."""
    _, model_with_tools = get_model()

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)

    if research_iterations >= max_researcher_iterations:
        return Command(goto=END, update=finalize_supervisor(state))

    print(supervisor_messages)
    system_message = lead_researcher_prompt.format(
        date=get_today_str(),
        max_researcher_iterations=max_researcher_iterations,
        max_concurrent_research_units=max_concurrent_researchers_unit,
    )

    messages = [SystemMessage(content=system_message)] + supervisor_messages
    response = await model_with_tools.ainvoke(messages)

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
        }
    )


async def supervisor_tools(state: SupervisorState) -> Command[Literal["supervisor", "__end__"]]:
    """Execute supervisor decisions - either conduct research or end the process."""
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    tool_messages = []
    all_raw_notes = []
    ui_messages = []
    next_step = "supervisor"
    trigger_search = state.get("trigger_search", False)
    should_end = False
    tool_calls = most_recent_message.tool_calls or []

    exceeded_iterations = research_iterations >= max_researcher_iterations
    no_tool_calls = not tool_calls

    research_complete = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in tool_calls
    )

    if exceeded_iterations or no_tool_calls or research_complete:
        should_end = True
        next_step = END

    else:
        current_step = "tool dispatch"
        try:
            think_tool_calls = [
                tc for tc in tool_calls
                if tc["name"] == "think_tool"
            ]
            conduct_research_calls = [
                tc for tc in tool_calls
                if tc["name"] == "ConductResearch"
            ]
            retriever_tool_calls = [
                tc for tc in tool_calls
                if tc["name"] == "retrieve_data_with_score"
            ]
            # Budget is gated on ConductResearch calls only — those spawn expensive
            # sub-agents. think_tool and retrieve_data_with_score are cheap local
            # operations and must not block research from starting.
            # All operations still count toward research_iterations to prevent loops.
            planned_research_steps = (
                len(think_tool_calls)
                + len(conduct_research_calls)
                + len(retriever_tool_calls)
            )
            remaining_budget = max_researcher_iterations - research_iterations

            if len(conduct_research_calls) > remaining_budget:
                should_end = True
                next_step = END
            else:
                updated_research_iterations = research_iterations + max(1, planned_research_steps)

                for tool_call in think_tool_calls:
                    current_step = "think_tool"
                    observations = think_tool.invoke(tool_call["args"])
                    tool_messages.append(ToolMessage(
                        content=observations,
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"]
                    ))

                for tool_call in retriever_tool_calls:
                    current_step = "retrieve_data_with_score"
                    observations = retrieve_data_with_score.invoke(state.get("research_brief", ""))
                    tool_messages.append(ToolMessage(
                        content=observations,
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"]
                    ))

                if conduct_research_calls:
                    current_step = "conduct_research_subagents"
                    coros = [
                        research_agent.ainvoke({
                            "researcher_messages": [HumanMessage(content=tc["args"]["research_topic"])],
                            "research_topic": tc["args"]["research_topic"]
                        }, config={
                            "configurable": {"thread_id": "1"},
                            "recursion_limit": 50,
                            "callbacks": [get_langfuse_callback()] if get_langfuse_callback() else []
                        })
                        for tc in conduct_research_calls
                    ]

                    tool_results = await asyncio.gather(*coros)

                    research_tool_messages = [
                        ToolMessage(
                            content=result.get("compressed_research", "Error synthesizing research report"),
                            name=tc["name"],
                            tool_call_id=tc["id"]
                        ) for result, tc in zip(tool_results, conduct_research_calls)
                    ]

                    tool_messages.extend(research_tool_messages)
                    all_raw_notes = [
                        "\n".join(result.get("raw_notes", []))
                        for result in tool_results
                    ]
                    ui_messages = [
                        message
                        for result in tool_results
                        for message in result.get("ui_messages", [])
                        if isinstance(message, str) and message.strip()
                    ]

                research_iterations = updated_research_iterations

        except Exception as e:
            print(f"Error in supervisor tools ({current_step}): {e}")
            return Command(
                goto=END,
                update={
                    **finalize_supervisor(state),
                    "workflow_error": f"Research workflow failed in supervisor tools ({current_step}): {e}",
                }
            )

    if should_end:
        return Command(
            goto=next_step,
            update=finalize_supervisor(state)
        )
    else:
        return Command(
            goto=next_step,
            update={
                "supervisor_messages": tool_messages,
                "raw_notes": all_raw_notes,
                "trigger_search": trigger_search,
                "ui_messages": ui_messages,
                "research_iterations": research_iterations,
            }
        )


supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")

supervisor_agent = supervisor_builder.compile()
