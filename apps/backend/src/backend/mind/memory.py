"""SQLite-backed persistent memory system for Minds with FTS5 full-text search."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional

from .database import init_db
from .schema import MemoryEntry


class MemoryManager:
    """Manages persistent memory for a Mind using SQLite + FTS5."""

    def __init__(self, db_path: Path):
        self._conn = init_db(db_path)
        self._lock = threading.Lock()

    def save(self, entry: MemoryEntry) -> str:
        """Persist a memory entry. Returns the memory ID."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO memories
                   (id, mind_id, content, category, relevance_keywords, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    entry.id,
                    entry.mind_id,
                    entry.content,
                    entry.category,
                    json.dumps(entry.relevance_keywords),
                    entry.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        return entry.id

    def retrieve(self, mind_id: str, memory_id: str) -> Optional[MemoryEntry]:
        """Load a specific memory by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE id = ? AND mind_id = ?",
                (memory_id, mind_id),
            ).fetchone()
        if row is None:
            return None
        return _row_to_memory(row)

    def search(self, mind_id: str, query: str, top_k: int = 10) -> list[MemoryEntry]:
        """Search memories using FTS5 full-text search."""
        fts_query = _build_fts_query(query)
        if not fts_query:
            return []

        with self._lock:
            rows = self._conn.execute(
                """SELECT m.* FROM memories m
                   JOIN memories_fts ON memories_fts.rowid = m.rowid
                   WHERE memories_fts MATCH ? AND m.mind_id = ?
                   ORDER BY memories_fts.rank
                   LIMIT ?""",
                (fts_query, mind_id, top_k),
            ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def list_all(self, mind_id: str, category: Optional[str] = None) -> list[MemoryEntry]:
        """List all memories for a Mind, optionally filtered by category."""
        with self._lock:
            if category is not None:
                rows = self._conn.execute(
                    "SELECT * FROM memories WHERE mind_id = ? AND category = ? ORDER BY created_at",
                    (mind_id, category),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM memories WHERE mind_id = ? ORDER BY created_at",
                    (mind_id,),
                ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def delete(self, mind_id: str, memory_id: str) -> bool:
        """Delete a specific memory."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM memories WHERE id = ? AND mind_id = ?",
                (memory_id, mind_id),
            )
            self._conn.commit()
        return cursor.rowcount > 0


def _row_to_memory(row: dict) -> MemoryEntry:
    return MemoryEntry(
        id=row["id"],
        mind_id=row["mind_id"],
        content=row["content"],
        category=row["category"],
        relevance_keywords=json.loads(row["relevance_keywords"]),
        created_at=row["created_at"],
    )


def _build_fts_query(query: str) -> str:
    """Convert a natural language query to an FTS5 OR query."""
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    if not tokens:
        return ""
    return " OR ".join(tokens)
