"""SQLite-backed persistence for Mind profiles and task history."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from .database import init_db
from .schema import MindProfile, Task


class MindStore:
    """Stores Mind profiles and task history in SQLite."""

    def __init__(self, db_path: Path):
        self._conn = init_db(db_path)
        self._lock = threading.Lock()

    def save_mind(self, mind: MindProfile) -> str:
        """Save a Mind profile. Returns the Mind ID."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO minds
                   (id, name, personality, preferences, system_prompt, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    mind.id,
                    mind.name,
                    mind.personality,
                    json.dumps(mind.preferences),
                    mind.system_prompt,
                    mind.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        return mind.id

    def load_mind(self, mind_id: str) -> Optional[MindProfile]:
        """Load a Mind profile by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM minds WHERE id = ?", (mind_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_mind(row)

    def list_minds(self) -> list[MindProfile]:
        """List all Mind profiles."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM minds ORDER BY created_at"
            ).fetchall()
        return [_row_to_mind(row) for row in rows]

    def delete_mind(self, mind_id: str) -> bool:
        """Delete a Mind profile."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM minds WHERE id = ?", (mind_id,)
            )
            self._conn.commit()
        return cursor.rowcount > 0

    def save_task(self, mind_id: str, task: Task) -> str:
        """Save a task to a Mind's task history."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (id, mind_id, description, status, result, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id,
                    mind_id,
                    task.description,
                    task.status,
                    task.result,
                    task.created_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                ),
            )
            self._conn.commit()
        return task.id

    def load_task(self, mind_id: str, task_id: str) -> Optional[Task]:
        """Load a specific task."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND mind_id = ?",
                (task_id, mind_id),
            ).fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    def list_tasks(self, mind_id: str) -> list[Task]:
        """List all tasks for a Mind, most recent first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE mind_id = ? ORDER BY created_at DESC",
                (mind_id,),
            ).fetchall()
        return [_row_to_task(row) for row in rows]

    def save_task_trace(self, mind_id: str, task_id: str, events: list[dict]) -> None:
        """Persist task execution trace events."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO task_traces (mind_id, task_id, events)
                   VALUES (?, ?, ?)""",
                (mind_id, task_id, json.dumps(events, default=str)),
            )
            self._conn.commit()

    def load_task_trace(self, mind_id: str, task_id: str) -> Optional[dict]:
        """Load a persisted task trace by task ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM task_traces WHERE mind_id = ? AND task_id = ?",
                (mind_id, task_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "mind_id": row["mind_id"],
            "task_id": row["task_id"],
            "events": json.loads(row["events"]),
        }


def _row_to_mind(row: dict) -> MindProfile:
    return MindProfile(
        id=row["id"],
        name=row["name"],
        personality=row["personality"],
        preferences=json.loads(row["preferences"]),
        system_prompt=row["system_prompt"],
        created_at=row["created_at"],
    )


def _row_to_task(row: dict) -> Task:
    return Task(
        id=row["id"],
        mind_id=row["mind_id"],
        description=row["description"],
        status=row["status"],
        result=row["result"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )
