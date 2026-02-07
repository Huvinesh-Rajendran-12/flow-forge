"""Shared execution state and trace models for the simulator."""

from datetime import datetime

from pydantic import BaseModel, Field


class SimulatorState(BaseModel):
    """Mutable state shared across all simulated services."""

    employees: dict[str, dict] = {}
    google_accounts: dict[str, dict] = {}
    slack_channels: dict[str, list[str]] = {}
    slack_users: set[str] = set()
    github_members: dict[str, dict] = {}
    jira_issues: dict[str, dict] = {}


class TraceStep(BaseModel):
    """A single step recorded during workflow execution."""

    node_id: str
    service: str
    action: str
    parameters: dict
    result: dict | None = None
    status: str  # "success" | "failed" | "skipped"
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ExecutionTrace(BaseModel):
    """Full trace of a workflow execution."""

    steps: list[TraceStep] = []
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
