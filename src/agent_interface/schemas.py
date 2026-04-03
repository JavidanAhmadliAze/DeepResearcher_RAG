from pydantic import BaseModel, Field

# OUTPUT SCHEMAS WHEN INVOKING LLM
class ClarifyWithUser(BaseModel):
    """Schema for user clarification decision and questions."""

    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question.",
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope",
    )
    verification: str = Field(
        description="Verify message that we will start research after the user has provided the necessary information.",
    )


class ResearchQuestion(BaseModel):
    """Schema for structured research brief generation."""

    research_brief: str = Field(
        description="A research question that will be used to guide the research."
    )

class GuardrailDecision(BaseModel):
    """Schema for guardrail agent decision on user input safety."""

    is_safe: bool = Field(
        description="Whether the user input is safe and appropriate for the research system.",
    )
    rejection_message: str = Field(
        description="Message to return to the user if the input is rejected. Empty string if safe.",
    )


class Summary(BaseModel):
    """Schema for webpage content summarization."""
    summary: str = Field(description="Concise summary of the webpage content")
    key_excerpts: str = Field(description="Important quotes and excerpts from the content")