"""
Quality dimension: Robustness
==============================
How does the agent handle the messiness of the real world?

Tests inject real adverse conditions — API timeouts, missing data, ambiguous
prompts — and verify the agent fails gracefully rather than crashing or
returning garbage.

Requires: DEEPSEEK_API_KEY, TAVILY_API_KEY
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, AIMessage


# ---------------------------------------------------------------------------
# Guardrail — handles empty message list without crashing
# ---------------------------------------------------------------------------

def test_guardrail_handles_empty_message_list():
    """Guardrail must not raise when there are no messages in state."""
    from src.agents.guardrail_agent import run_guardrail

    result = asyncio.run(run_guardrail({"messages": []}))
    # Should return a valid decision, not crash
    assert hasattr(result, "is_safe")


# ---------------------------------------------------------------------------
# Guardrail — handles very long input without crashing
# ---------------------------------------------------------------------------

def test_guardrail_handles_very_long_input():
    """Guardrail must handle inputs near or above typical context limits gracefully."""
    from src.agents.guardrail_agent import run_guardrail

    # ~4 000 words of repeated text to stress the prompt
    long_input = ("What are the implications of quantum computing for cybersecurity? " * 60).strip()
    state = {"messages": [HumanMessage(content=long_input)]}

    result = asyncio.run(run_guardrail(state))
    assert hasattr(result, "is_safe"), "Guardrail crashed on long input"


# ---------------------------------------------------------------------------
# Research agent — handles Tavily returning no results
# ---------------------------------------------------------------------------

def test_research_agent_handles_empty_search_results():
    """Research agent must not crash when a search returns an empty result."""
    from src.agents.research_agent import research_agent

    with patch("src.agents.research_agent.tools_by_name") as mock_tools:
        mock_tool = AsyncMock()
        mock_tool.invoke = lambda args: "No results found."
        mock_tools.__getitem__ = lambda self, name: mock_tool
        mock_tools.__contains__ = lambda self, name: True

        topic = "Some extremely obscure topic with no web results"
        state = {
            "researcher_messages": [HumanMessage(content=topic)],
            "research_topic": topic,
        }

        result = asyncio.run(
            research_agent.ainvoke(state, config={"recursion_limit": 50})
        )

    # Should produce some output even with empty search results
    compressed = result.get("compressed_research", "")
    assert isinstance(compressed, str), "compressed_research must be a string even on empty results"


# ---------------------------------------------------------------------------
# Research agent — handles a sub-agent model timeout gracefully
# ---------------------------------------------------------------------------

def test_supervisor_handles_research_subagent_timeout():
    """Supervisor must set workflow_error and not re-raise when a sub-agent times out."""
    from src.agents.supervisor_agent import supervisor_tools
    from langgraph.graph import END

    conduct_call = {
        "name": "ConductResearch",
        "args": {"research_topic": "Timeout simulation topic"},
        "id": "tc-timeout",
    }
    last_message = AIMessage(content="")
    last_message.tool_calls = [conduct_call]

    state = {
        "supervisor_messages": [last_message],
        "research_brief": "Timeout test brief",
        "research_iterations": 0,
        "trigger_search": False,
    }

    with patch("src.agents.supervisor_agent.research_agent") as mock_agent:
        mock_agent.ainvoke = AsyncMock(side_effect=TimeoutError("DeepSeek API timed out"))
        command = asyncio.run(supervisor_tools(state))

    assert command.goto == END, "Supervisor must end the workflow on timeout, not hang"
    assert "workflow_error" in command.update, "workflow_error must be set after timeout"


# ---------------------------------------------------------------------------
# Full workflow — ambiguous prompt handled without crash
# ---------------------------------------------------------------------------

def test_workflow_handles_ambiguous_prompt_gracefully():
    """Workflow must handle a vague prompt without crashing — either ask for
    clarification or produce a reasonable report."""
    from src.agents.workflow_executor import deep_researcher_agent

    vague_query = "Tell me more."
    state = {"messages": [HumanMessage(content=vague_query)]}

    result = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-robustness-1"}, "recursion_limit": 100},
        )
    )

    has_report = bool(result.get("final_report", "").strip())
    needs_clarification = bool(result.get("needs_clarification"))
    is_guardrail_rejection = result.get("workflow_error") == "guardrail_rejected"

    assert has_report or needs_clarification or is_guardrail_rejection, (
        f"Workflow returned no useful output for an ambiguous prompt. Result keys: {list(result.keys())}"
    )


# ---------------------------------------------------------------------------
# Full workflow — repeated identical queries do not compound state
# ---------------------------------------------------------------------------

def test_workflow_handles_repeated_query_without_state_leak():
    """Running the same query twice must not produce an error on the second run."""
    from src.agents.workflow_executor import deep_researcher_agent

    query = "What is the CAP theorem in distributed systems?"
    state = {"messages": [HumanMessage(content=query)]}

    # First run
    result_1 = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-robustness-2a"}, "recursion_limit": 100},
        )
    )
    assert result_1.get("final_report"), "First run produced no report"

    # Second run — fresh state, should behave identically
    result_2 = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-robustness-2b"}, "recursion_limit": 100},
        )
    )
    assert result_2.get("final_report"), "Second run produced no report"
    assert result_2.get("workflow_error") != "guardrail_rejected"


# ---------------------------------------------------------------------------
# Model wrapper — structured output retry on genuinely bad real response
# ---------------------------------------------------------------------------

def test_ainvoke_structured_recovers_from_malformed_first_response():
    """ainvoke_structured must succeed when the first real model response is
    accidentally malformed (simulated by poisoning the first call only)."""
    import json
    from src.llm.model_wrapper import ainvoke_structured, create_model
    from src.agent_interface.schemas import GuardrailDecision

    real_model = create_model("guardrail_agent")
    original_ainvoke = real_model.ainvoke
    call_count = {"n": 0}

    async def poisoned_ainvoke(messages, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Return intentionally broken JSON on the first attempt
            return AIMessage(content="Sorry, I cannot answer that. {broken json")
        return await original_ainvoke(messages, **kwargs)

    messages = [HumanMessage(content="Is this a safe research question about climate change?")]
    with patch.object(real_model, "ainvoke", side_effect=poisoned_ainvoke):
        result = asyncio.run(ainvoke_structured(real_model, GuardrailDecision, messages))

    assert isinstance(result, GuardrailDecision), "Did not recover from malformed first response"
    assert call_count["n"] >= 2, "Retry was never triggered"
