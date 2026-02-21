"""File-based persistence for Mind profiles and task history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .persistence import FileLock, atomic_write_text
from .schema import MindProfile, Task


class MindStore:
    """Stores Mind profiles and task history as JSON files."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.minds_dir = base_dir / "minds"
        self.tasks_dir = base_dir / "tasks"
        self.traces_dir = base_dir / "traces"
        self.minds_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(base_dir / ".mind_store.lock")

    def save_mind(self, mind: MindProfile) -> str:
        """Save a Mind profile. Returns the Mind ID."""
        with self._lock.locked():
            filepath = self.minds_dir / f"{mind.id}.json"
            atomic_write_text(filepath, mind.model_dump_json(indent=2))
        return mind.id

    def load_mind(self, mind_id: str) -> Optional[MindProfile]:
        """Load a Mind profile by ID."""
        with self._lock.locked():
            filepath = self.minds_dir / f"{mind_id}.json"
            if not filepath.exists():
                return None
            data = json.loads(filepath.read_text())
            return MindProfile.model_validate(data)

    def list_minds(self) -> list[MindProfile]:
        """List all Mind profiles."""
        with self._lock.locked():
            minds: list[MindProfile] = []
            for filepath in sorted(self.minds_dir.glob("*.json")):
                data = json.loads(filepath.read_text())
                minds.append(MindProfile.model_validate(data))
            return minds

    def delete_mind(self, mind_id: str) -> bool:
        """Delete a Mind profile."""
        with self._lock.locked():
            filepath = self.minds_dir / f"{mind_id}.json"
            if filepath.exists():
                filepath.unlink()
                return True
            return False

    def _task_dir(self, mind_id: str, *, create: bool = False) -> Path:
        d = self.tasks_dir / mind_id
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def save_task(self, mind_id: str, task: Task) -> str:
        """Save a task to a Mind's task history."""
        with self._lock.locked():
            task_dir = self._task_dir(mind_id, create=True)
            filepath = task_dir / f"{task.id}.json"
            atomic_write_text(filepath, task.model_dump_json(indent=2))
        return task.id

    def load_task(self, mind_id: str, task_id: str) -> Optional[Task]:
        """Load a specific task."""
        with self._lock.locked():
            filepath = self._task_dir(mind_id) / f"{task_id}.json"
            if not filepath.exists():
                return None
            data = json.loads(filepath.read_text())
            return Task.model_validate(data)

    def list_tasks(self, mind_id: str) -> list[Task]:
        """List all tasks for a Mind, most recent first."""
        with self._lock.locked():
            task_dir = self._task_dir(mind_id)
            if not task_dir.exists():
                return []

            tasks: list[Task] = []
            for filepath in task_dir.glob("*.json"):
                data = json.loads(filepath.read_text())
                tasks.append(Task.model_validate(data))

            tasks.sort(key=lambda task: task.created_at, reverse=True)
            return tasks

    def _trace_dir(self, mind_id: str, *, create: bool = False) -> Path:
        d = self.traces_dir / mind_id
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def save_task_trace(self, mind_id: str, task_id: str, events: list[dict]) -> None:
        """Persist task execution trace events."""
        with self._lock.locked():
            trace_file = self._trace_dir(mind_id, create=True) / f"{task_id}.json"
            payload = {
                "mind_id": mind_id,
                "task_id": task_id,
                "events": events,
            }
            atomic_write_text(trace_file, json.dumps(payload, indent=2, default=str))

    def load_task_trace(self, mind_id: str, task_id: str) -> Optional[dict]:
        """Load a persisted task trace by task ID."""
        with self._lock.locked():
            trace_file = self._trace_dir(mind_id) / f"{task_id}.json"
            if not trace_file.exists():
                return None
            return json.loads(trace_file.read_text())
