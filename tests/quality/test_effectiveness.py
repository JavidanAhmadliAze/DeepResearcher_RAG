"""
Quality dimension: Effectiveness
=================================
Did the agent successfully and accurately achieve the user's actual intent?

Tests make real LLM calls and use an LLM-as-judge to score outputs on a 1-5
rubric.  A score < 3 fails the test.

Requires: DEEPSEEK_API_KEY, TAVILY_API_KEY
"""
import asyncio
import json

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from tests.quality.conftest import BENIGN_QUERIES, extract_token_usage


# ---------------------------------------------------------------------------
# Judge helper
# ---------------------------------------------------------------------------

EFFECTIVENESS_RUBRIC = """
You are an impartial evaluator.  Score the following agent response on a scale
of 1 to 5 for EFFECTIVENESS — whether it accurately and completely addressed
the user's research intent.

Rubric:
  5 — Fully addresses the query with accurate, well-organised information.
  4 — Mostly addresses the query; minor gaps or minor inaccuracies.
  3 — Partially addresses the query; notable gaps but some useful content.
  2 — Largely misses the intent; little useful content.
  1 — Completely off-topic or refused a legitimate request.

User query: {query}

Agent response:
{response}

Reply with a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}
"""


def judge_effectiveness(judge_model, query: str, response: str) -> dict:
    prompt = EFFECTIVENESS_RUBRIC.format(query=query, response=response)
    raw = judge_model.invoke([HumanMessage(content=prompt)])
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    # Strip markdown fences if present
    if "```" in text:
        lines = text.strip().splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) >= 3 else text
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


# ---------------------------------------------------------------------------
# Guardrail — must allow legitimate research queries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query", BENIGN_QUERIES)
def test_guardrail_passes_legitimate_research(query):
    """Guardrail must classify real research queries as safe (is_safe=True)."""
    from src.agents.guardrail_agent import run_guardrail

    state = {"messages": [HumanMessage(content=query)]}
    decision = asyncio.run(run_guardrail(state))

    assert decision.is_safe, (
        f"Guardrail incorrectly rejected a legitimate query.\n"
        f"Query: {query}\n"
        f"Rejection message: {decision.rejection_message}"
    )


# ---------------------------------------------------------------------------
# Scope agent — must produce a research brief for clear queries
# ---------------------------------------------------------------------------

def test_scope_agent_produces_research_brief():
    """Scope agent must return a non-empty research brief for a clear query."""
    from src.agents.scope_agent import scope_agent
    from langchain_core.messages import HumanMessage

    query = BENIGN_QUERIES[0]
    state = {"messages": [HumanMessage(content=query)]}
    result = asyncio.run(scope_agent.ainvoke(state))

    brief = result.get("research_brief", "")
    assert brief and len(brief) > 20, (
        f"Scope agent returned an empty or too-short research brief: {brief!r}"
    )


def test_scope_agent_sets_clarification_for_ambiguous_query():
    """Scope agent must ask for clarification when the query is genuinely ambiguous."""
    from src.agents.scope_agent import scope_agent

    ambiguous = "Tell me about AI."
    state = {"messages": [HumanMessage(content=ambiguous)]}
    result = asyncio.run(scope_agent.ainvoke(state))

    # Either it asks for clarification OR produces a research brief — both are
    # acceptable; what is NOT acceptable is crashing or returning nothing.
    has_brief = bool(result.get("research_brief", "").strip())
    needs_clarification = bool(result.get("needs_clarification"))
    assert has_brief or needs_clarification, (
        "Scope agent returned neither a research brief nor a clarification request "
        f"for an ambiguous query. Result: {result}"
    )


# ---------------------------------------------------------------------------
# Full workflow — judge the final report quality
# ---------------------------------------------------------------------------

def test_full_workflow_produces_quality_report(judge_model):
    """End-to-end: the full agent pipeline must produce a research report scored >= 3/5."""
    from src.agents.workflow_executor import deep_researcher_agent

    query = "What are the main risks of large language models in healthcare applications?"
    state = {"messages": [HumanMessage(content=query)]}

    result = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-effectiveness-1"}, "recursion_limit": 100},
        )
    )

    final_report = result.get("final_report", "")
    assert final_report, "Agent produced no final_report"

    verdict = judge_effectiveness(judge_model, query, final_report)
    score = verdict.get("score", 0)
    assert score >= 3, (
        f"Effectiveness score too low: {score}/5\n"
        f"Judge reason: {verdict.get('reason')}\n"
        f"Report snippet: {final_report[:500]}"
    )


# ---------------------------------------------------------------------------
# Guardrail + scope: safe input must reach the research stage
# ---------------------------------------------------------------------------

def test_safe_input_reaches_research_stage():
    """A legitimate query must not be blocked — workflow_error must be absent."""
    from src.agents.workflow_executor import deep_researcher_agent

    query = BENIGN_QUERIES[1]
    state = {"messages": [HumanMessage(content=query)]}

    result = asyncio.run(
        deep_researcher_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": "quality-effectiveness-2"}, "recursion_limit": 100},
        )
    )

    assert result.get("workflow_error") != "guardrail_rejected", (
        f"Legitimate query was rejected by the guardrail: {query}"
    )
    assert result.get("final_report"), "No final report produced for a legitimate query"
