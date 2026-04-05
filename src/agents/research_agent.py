from src.utils.tools import get_today_str, think_tool, tavily_search
from langgraph.graph import StateGraph, START, END
from src.agent_interface.states import ResearcherState, ResearcherOutputState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, filter_messages
from typing_extensions import Literal
from threading import Lock
from src.llm.model_wrapper import create_model
from src.prompt_engineering.templates import get_prompt

# Prompts are safe to load at module level (no NAT dependency)
research_agent_prompt = get_prompt("research_agent", "research_agent_prompt")
compress_research_system_prompt = get_prompt("research_agent", "compress_research_system_prompt")
compress_research_human_message = get_prompt("research_agent", "compress_research_human_message")

import re

tools = [tavily_search, think_tool]
tools_by_name = {tool.name: tool for tool in tools}


def _format_search_ui_message(query: str, observation: str) -> str:
    """Build a clean intermediate UI message from a Tavily search result.

    Extracts source titles from the formatted observation string and returns
    a short, human-readable summary — no XML/HTML tags, no raw content.
    """
    titles = re.findall(r"--- SOURCE \d+: (.+?) ---", observation)
    header = f'Searching: "{query}"'
    if not titles:
        return header
    bullet_list = "\n".join(f"  - {title.strip()}" for title in titles)
    return f"{header}\n\nSources found:\n{bullet_list}"
max_research_iterations = 4

# Lazy initialization — model is None until first use inside NAT's runtime context
_model = None
_model_with_tools = None
_model_lock = Lock()


def get_model():
    """Lazily initialize the model and model_with_tools on first call."""
    global _model, _model_with_tools

    # Fast path when already initialized.
    if _model is not None and _model_with_tools is not None:
        return _model, _model_with_tools

    # Parallel research runs can hit this path concurrently, so guard lazy init.
    with _model_lock:
        if _model is None:
            _model = create_model("research_agent")
        if _model_with_tools is None:
            _model_with_tools = _model.bind_tools(tools)

    if _model is None or _model_with_tools is None:
        raise RuntimeError("Failed to initialize research agent model bindings")

    return _model, _model_with_tools


async def llm_call(state: ResearcherState):
    """Analyze current state and decide on next actions.

    The model analyzes the current conversation state and decides whether to:
    1. Call search tools to gather more information
    2. Provide a final answer based on gathered information

    Returns updated state with the model's response.
    """
    _, model_with_tools = get_model()
    return {
        "researcher_messages": [
            await model_with_tools.ainvoke(
                [SystemMessage(content=research_agent_prompt)] + state.get("researcher_messages", [])
            )
        ]
    }


async def tool_node(state: ResearcherState):
    """Execute all tool calls from the previous LLM response and show outputs."""

    tool_calls = state["researcher_messages"][-1].tool_calls
    observations = []
    ui_messages = []

    MAX_TOOL_CHARS = 12_000  # ~3,000 tokens per tool result

    for tool_call in tool_calls:
        tool_name = getattr(tool_call, "name", tool_call.get("name"))
        tool_args = getattr(tool_call, "args", tool_call.get("args"))

        t = tools_by_name[tool_name]
        observation = await t.ainvoke(tool_args)

        if isinstance(observation, str) and len(observation) > MAX_TOOL_CHARS:
            observation = observation[:MAX_TOOL_CHARS] + "\n[truncated]"

        observations.append(observation)
        if tool_name == "tavily_search" and isinstance(observation, str) and observation.strip():
            query = tool_args.get("query", "") if isinstance(tool_args, dict) else ""
            ui_messages.append(_format_search_ui_message(query, observation))

    # Create ToolMessage objects for the next model input
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) for observation, tool_call in zip(observations, tool_calls)
    ]

    return {
        "researcher_messages": tool_outputs,
        "ui_messages": ui_messages,
        "research_iterations": state.get("research_iterations", 0) + 1,
    }


async def compress_research(state: ResearcherState) -> dict:
    """Compress research findings into a concise summary.

    Takes all the research messages and tool outputs and creates
    a compressed summary suitable for the supervisor's decision-making.
    """
    model, _ = get_model()

    system_message = compress_research_system_prompt.format(date=get_today_str())

    researcher_messages = state.get("researcher_messages", [])

    # If we stop because of iteration budget right after an LLM tool-call turn,
    # the trailing AI tool_calls message has no matching ToolMessage yet.
    # Drop that dangling turn before invoking the model again.
    if researcher_messages and getattr(researcher_messages[-1], "tool_calls", None):
        researcher_messages = researcher_messages[:-1]

    messages = (
        [SystemMessage(content=system_message)]
        + researcher_messages
        + [HumanMessage(content=compress_research_human_message)]
    )
    response = await model.ainvoke(messages)

    # Extract raw notes from tool and AI messages
    raw_notes = [
        str(m.content) for m in filter_messages(
            researcher_messages,
            include_types=["tool", "ai", "ToolMessage", "AIMessage"]
        )
    ]

    return {
        "compressed_research": str(response.content),
        "raw_notes": ["\n".join(raw_notes)]
    }


def _search_results_are_redundant(messages: list) -> bool:
    """Return True if the last two tavily search ToolMessages have >80% character overlap."""
    search_results = [
        m.content for m in messages
        if isinstance(m, ToolMessage) and getattr(m, "name", "") == "tavily_search"
    ]
    if len(search_results) < 2:
        return False
    a, b = search_results[-2], search_results[-1]
    if not a or not b:
        return False
    shorter = min(len(a), len(b))
    # Count common characters at matching positions
    overlap = sum(ca == cb for ca, cb in zip(a, b))
    return (overlap / shorter) > 0.8


def should_continue(state: ResearcherState) -> Literal["tool_node", "compress_research"]:
    """Determine whether to continue research or provide final answer.

    Returns:
        "tool_node": Continue to tool execution
        "compress_research": Stop and compress research
    """
    messages = state["researcher_messages"]
    last_message = messages[-1]
    completed_iterations = state.get("research_iterations", 0)

    if completed_iterations >= max_research_iterations:
        return "compress_research"

    # Stop early if last two searches returned near-identical results
    if _search_results_are_redundant(messages):
        return "compress_research"

    if last_message.tool_calls:
        return "tool_node"
    return "compress_research"


agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

# Add nodes to the graph
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("compress_research", compress_research)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",                  # Continue research loop
        "compress_research": "compress_research",  # Provide final answer
    },
)
agent_builder.add_edge("tool_node", "llm_call")  # Loop back for more research
agent_builder.add_edge("compress_research", END)

research_agent = agent_builder.compile()
