"""API models for FlowForge."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    """Request to generate or modify a workflow."""

    description: str = Field(
        ..., description="Natural language description of the desired workflow"
    )
    context: Optional[dict[str, Any]] = Field(
        None,
        description="Additional context (e.g., employee name, department, systems)",
    )
    team: str = Field(
        "default",
        description="Team whose knowledge base to use",
    )
    workflow_id: Optional[str] = Field(
        None,
        description="If provided, modify this existing workflow instead of creating new",
    )


class StreamMessage(BaseModel):
    """A single streamed message from the agent."""

    type: str = Field(..., description="Message type: text, tool_use, result, error")
    content: Any = Field(..., description="Message content")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str = "FlowForge Backend"
