"""Execution report model with markdown rendering."""

from ..simulator.state import ExecutionTrace
from pydantic import BaseModel


class ExecutionReport(BaseModel):
    """Summary of a workflow execution run."""

    workflow_id: str
    workflow_name: str
    total_steps: int
    successful: int
    failed: int
    skipped: int
    trace: ExecutionTrace
    dependency_violations: list[str] = []

    def to_markdown(self) -> str:
        lines = [
            f"# Execution Report: {self.workflow_name}",
            "",
            f"**Workflow ID:** `{self.workflow_id}`",
            f"**Total steps:** {self.total_steps}",
            f"**Successful:** {self.successful}",
            f"**Failed:** {self.failed}",
            f"**Skipped:** {self.skipped}",
            "",
        ]

        if self.dependency_violations:
            lines.append("## Dependency Violations")
            for v in self.dependency_violations:
                lines.append(f"- {v}")
            lines.append("")

        lines.append("## Execution Trace")
        lines.append("")
        lines.append("| # | Node | Service | Action | Status | Detail |")
        lines.append("|---|------|---------|--------|--------|--------|")

        for i, step in enumerate(self.trace.steps, 1):
            detail = ""
            if step.status == "success" and step.result:
                # Show a compact summary of the result
                detail = ", ".join(f"{k}={v}" for k, v in step.result.items() if k != "status")
            elif step.error:
                detail = step.error

            status_icon = {"success": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(
                step.status, step.status
            )
            lines.append(
                f"| {i} | `{step.node_id}` | {step.service} | {step.action} | {status_icon} | {detail} |"
            )

        lines.append("")
        if self.trace.started_at and self.trace.completed_at:
            duration = (self.trace.completed_at - self.trace.started_at).total_seconds()
            lines.append(f"**Duration:** {duration:.2f}s")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
