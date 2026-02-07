"""File based workflow storage organized by team."""

import json
from pathlib import Path

from .schema import Workflow


class WorkflowStore:
    """Stores workflows as JSON files, organized by team."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def save(self, workflow: Workflow) -> str:
        """Save a workflow and return its ID."""
        team_dir = self.base_dir / workflow.team
        team_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{workflow.id}-v{workflow.version}.json"
        filepath = team_dir / filename
        filepath.write_text(workflow.model_dump_json(indent=2))
        return workflow.id

    def load(self, workflow_id: str, team: str = "default") -> Workflow | None:
        """Load the latest version of a workflow by ID."""
        team_dir = self.base_dir / team
        if not team_dir.exists():
            return None

        # Find the latest version
        matches = sorted(team_dir.glob(f"{workflow_id}-v*.json"), reverse=True)
        if not matches:
            return None

        data = json.loads(matches[0].read_text())
        return Workflow.model_validate(data)

    def list_by_team(self, team: str) -> list[Workflow]:
        """List all workflows for a team."""
        team_dir = self.base_dir / team
        if not team_dir.exists():
            return []

        workflows = []
        seen_ids: set[str] = set()
        for filepath in sorted(team_dir.glob("*.json"), reverse=True):
            data = json.loads(filepath.read_text())
            wf = Workflow.model_validate(data)
            if wf.id not in seen_ids:
                seen_ids.add(wf.id)
                workflows.append(wf)
        return workflows

    def delete(self, workflow_id: str, team: str = "default") -> bool:
        """Delete all versions of a workflow. Returns True if any were deleted."""
        team_dir = self.base_dir / team
        if not team_dir.exists():
            return False

        matches = list(team_dir.glob(f"{workflow_id}-v*.json"))
        for f in matches:
            f.unlink()
        return len(matches) > 0
