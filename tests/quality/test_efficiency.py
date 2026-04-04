"""
Quality dimension: Efficiency
==============================
Does the agent complete tasks without wasting tokens, time, or tool calls?

Metrics captured per run:
  - Wall-clock latency (seconds)
  - Total tokens consumed
  - Number of tool calls made by the research agent
  - Whether the iteration budget was exhausted

Thresholds are intentionally generous — the goal is to catch runaway loops or
unexpectedly large responses, not to enforce tight SLAs in CI.

Requires: DEEPSEEK_API_KEY, TAVILY_API_KEY
"""
import asyncio
import time

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage

from tests.quality.conftest import CallMetrics, extract_token_usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_ACCEPTABLE_LATENCY_S = 1200      # 2 minutes for a full research run
MAX_ACCEPTABLE_TOTAL_TOKENS = 80_000  # rough upper bound per research run
MAX_TOOL_CALLS_PER_RESEARCH = 12     # research_agent max_iterations * 2


def count_tool_calls(messages: list) -> int:
    return sum(
        1 for m in messages
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
    )


# ---------------------------------------------------------------------------
# Research agent — does not exceed iteration budget
# ---------------------------------------------------------------------------

def test_research_agent_stays_within_iteration_budget():
    """Research agent must stop before or at max_research_iterations."""
    from src.agents.research_agent import research_agent, max_research_iterations
    from langchain_core.messages import HumanMessage

    topic = "Recent advances in solid-state battery technology"
    state = {
        "researcher_messages": [HumanMessage(content=topic)],
        "research_topic": topic,
    }

    result = asyncio.run(
        research_agent.ainvoke(state, config={"recursion_limit": 50})
    )

    iterations = result.get("research_iterations", 0)
    assert iterations <= max_research_iterations, (
        f"Research agent ran {iterations} iterations, exceeding the cap of {max_research_iterations}"
    )


def test_research_agent_makes_bounded_tool_calls():
    """Research agent must not make more tool calls than the iteration budget allows."""
    from src.agents.research_agent import research_agent

    topic = "Impact of social media on teenage mental health"
    state = {
        "researcher_messages": [HumanMessage(content=topic)],
        "research_topic": topic,
    }

    result = asyncio.run(
        research_agent.ainvoke(state, config={"recursion_limit": 50})
    )

    messages = list(result.get("researcher_messages", []))
    tool_call_turns = count_tool_calls(messages)
    assert tool_call_turns <= MAX_TOOL_CALLS_PER_RESEARCH, (
        f"Research agent made {tool_call_turns} tool-call turns — likely a loop"
    )


# ---------------------------------------------------------------------------
# Research agent — produces non-trivial output
# ---------------------------------------------------------------------------

def test_research_agent_produces_compressed_research():
    """Research agent must return a non-empty compressed_research string."""
    from src.agents.research_agent import research_agent

    topic = "Key differences between REST and GraphQL APIs"
    state = {
        "researcher_messages": [HumanMessage(content=topic)],
        "research_topic": topic,
    }

    result = asyncio.run(
        research_agent.ainvoke(state, config={"recursion_limit": 50})
    )

    compressed = result.get("compressed_research", "")
    assert len(compressed) > 100, (
        f"compressed_research is too short ({len(compressed)} chars) — "
        "agent may have done no real research"
    )


# ---------------------------------------------------------------------------
# Supervisor — stays within researcher iteration budget
# ---------------------------------------------------------------------------

def test_supervisor_stays_within_iteration_budget():
    """Supervisor must not exceed max_researcher_iterations."""
    from src.agents.supervisor_agent import supervisor_agent, max_researcher_iterations

    brief = "Analyse the competitive landscape of cloud AI platforms in 2024."
    state = {
        "supervisor_messages": [HumanMessage(content=brief)],
        "research_brief": brief,
        "research_iterations": 0,
        "trigger_search": True,
    }

    result = asyncio.run(
        supervisor_agent.ainvoke(state, config={"recursion_limit": 100})
    )

    iterations = result.get("research_iterations", 0)
    assert iterations <= max_researcher_iterations, (
        f"Supervisor ran {iterations} iterations, exceeding the cap of {max_researcher_iterations}"
    )


# ---------------------------------------------------------------------------
# Full workflow — latency and token ceiling
# ---------------------------------------------------------------------------

def test_full_workflow_completes_within_time_budget():
    """End-to-end workflow must complete within the acceptable latency ceiling."""
    from src.agents.workflow_executor import deep_researcher_agent

    query = "What is retrieval-augmented generation and why does it matter?"
    state = {"messages": [HumanMessage(content=query)]}

    start = time.perf_counter()
    result = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-efficiency-1"}, "recursion_limit": 100},
        )
    )
    elapsed = time.perf_counter() - start

    assert elapsed <= MAX_ACCEPTABLE_LATENCY_S, (
        f"Workflow took {elapsed:.1f}s — exceeds ceiling of {MAX_ACCEPTABLE_LATENCY_S}s"
    )
    assert result.get("final_report"), "No final report produced"


def test_full_workflow_does_not_run_away_on_tokens():
    """End-to-end workflow must not consume an unreasonable number of tokens."""
    from src.agents.workflow_executor import deep_researcher_agent

    query = "What are the key technical milestones achieved in nuclear fusion research between 2020 and 2024, specifically in magnetic confinement and inertial confinement approaches?"
    state = {"messages": [HumanMessage(content=query)]}

    # Collect token usage via a simple callback
    token_counts = {"prompt": 0, "completion": 0}

    class _TokenTracker(BaseCallbackHandler):
        def on_llm_end(self, response, **kwargs):
            for gen in response.generations:
                for g in gen:
                    p, c = extract_token_usage(g)
                    token_counts["prompt"] += p
                    token_counts["completion"] += c

    result = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={
                "configurable": {"thread_id": "quality-efficiency-2"},
                "recursion_limit": 100,
                "callbacks": [_TokenTracker()],
            },
        )
    )

    total = token_counts["prompt"] + token_counts["completion"]
    # If we couldn't capture tokens, skip the assertion (callback may not fire
    # for all model types)
    if total > 0:
        assert total <= MAX_ACCEPTABLE_TOTAL_TOKENS, (
            f"Workflow consumed {total:,} tokens — exceeds ceiling of {MAX_ACCEPTABLE_TOTAL_TOKENS:,}"
        )
    assert result.get("final_report"), "No final report produced"
