"""
Custom exception hierarchy for the Deep Research Assistant.

All exceptions derive from DeepResearchException so callers can catch the
entire family with a single except clause when broad handling is needed.
"""


class DeepResearchException(Exception):
    """Base exception for all Deep Research Assistant errors."""


# ---------------------------------------------------------------------------
# Agent-level exceptions
# ---------------------------------------------------------------------------

class AgentException(DeepResearchException):
    """Raised when an agent fails to complete its task."""


class GuardrailException(AgentException):
    """Raised when the guardrail agent rejects a user request.

    Attributes:
        rejection_message: Human-readable reason returned to the user.
    """

    def __init__(self, rejection_message: str) -> None:
        super().__init__(rejection_message)
        self.rejection_message = rejection_message


class ModelInvocationException(AgentException):
    """Raised when an LLM API call fails (network error, auth, rate limit, etc.).

    Attributes:
        agent_name: Identifier of the agent that triggered the call.
        cause: The underlying exception from the LLM client library.
    """

    def __init__(self, agent_name: str, cause: Exception) -> None:
        super().__init__(f"Model invocation failed for agent '{agent_name}': {cause}")
        self.agent_name = agent_name
        self.cause = cause


class StructuredOutputException(AgentException):
    """Raised when structured JSON output cannot be parsed from the model response.

    Attributes:
        schema_name: Name of the Pydantic schema that was expected.
        raw_response: The raw text returned by the model.
        cause: The underlying parse/validation error.
    """

    def __init__(self, schema_name: str, raw_response: str, cause: Exception) -> None:
        super().__init__(
            f"Failed to parse '{schema_name}' from model output after retries: {cause}"
        )
        self.schema_name = schema_name
        self.raw_response = raw_response
        self.cause = cause


class ResearchAgentException(AgentException):
    """Raised when a research sub-agent fails to complete its assigned topic.

    Attributes:
        research_topic: The topic that was being investigated.
        cause: The underlying error.
    """

    def __init__(self, research_topic: str, cause: Exception) -> None:
        super().__init__(
            f"Research agent failed on topic '{research_topic}': {cause}"
        )
        self.research_topic = research_topic
        self.cause = cause


class SupervisorException(AgentException):
    """Raised when the supervisor agent encounters an unrecoverable error.

    Attributes:
        step: The workflow step where the failure occurred (e.g. 'think_tool').
        cause: The underlying error.
    """

    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"Supervisor failed at step '{step}': {cause}")
        self.step = step
        self.cause = cause


# ---------------------------------------------------------------------------
# Workflow-level exceptions
# ---------------------------------------------------------------------------

class WorkflowException(DeepResearchException):
    """Raised when the overall multi-agent workflow cannot proceed.

    Attributes:
        step: The workflow node where execution broke down.
        cause: The underlying error, if any.
    """

    def __init__(self, step: str, cause: Exception | None = None) -> None:
        detail = f": {cause}" if cause else ""
        super().__init__(f"Workflow failed at step '{step}'{detail}")
        self.step = step
        self.cause = cause


class BudgetExhaustedException(WorkflowException):
    """Raised when the research iteration budget is exhausted before completion.

    Attributes:
        max_iterations: The configured limit that was reached.
    """

    def __init__(self, max_iterations: int) -> None:
        super().__init__(
            step="budget_check",
            cause=None,
        )
        self.max_iterations = max_iterations
        self.args = (f"Research iteration budget of {max_iterations} exhausted",)


# ---------------------------------------------------------------------------
# Infrastructure exceptions
# ---------------------------------------------------------------------------

class ConfigurationException(DeepResearchException):
    """Raised when required configuration (env vars, YAML keys) is missing or invalid.

    Attributes:
        key: The missing or invalid configuration key.
    """

    def __init__(self, key: str, detail: str = "") -> None:
        msg = f"Invalid or missing configuration for '{key}'"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
        self.key = key


class RetrieverException(DeepResearchException):
    """Raised when the vector-store retriever fails to fetch results.

    Attributes:
        query: The retrieval query that caused the failure.
        cause: The underlying error.
    """

    def __init__(self, query: str, cause: Exception) -> None:
        super().__init__(f"Retriever failed for query '{query[:80]}': {cause}")
        self.query = query
        self.cause = cause
