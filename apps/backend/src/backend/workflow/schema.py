"""Pydantic models defining the workflow DAG structure."""

from typing import Any

from pydantic import BaseModel


class NodeParameter(BaseModel):
    """A single parameter for a workflow node."""

    name: str
    value: Any
    description: str
    required: bool = True


class WorkflowNode(BaseModel):
    """A single step in the workflow DAG."""

    id: str
    name: str
    description: str
    service: str  # "slack" | "jira" | "google" | "hr" | "github"
    action: str  # "create_channel" | "send_message" | etc.
    actor: str  # "hr_manager" | "it_admin" | "team_lead"
    parameters: list[NodeParameter] = []
    depends_on: list[str] = []
    outputs: dict[str, str] = {}


class WorkflowEdge(BaseModel):
    """An explicit edge between two workflow nodes."""

    source: str
    target: str


class Workflow(BaseModel):
    """A complete workflow DAG."""

    id: str
    name: str
    description: str
    team: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge] = []
    parameters: dict[str, Any] = {}
    version: int = 1
