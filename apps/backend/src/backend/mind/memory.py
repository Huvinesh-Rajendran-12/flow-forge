"""Persistent memory system for Minds."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .persistence import FileLock, atomic_write_text
from .schema import MemoryEntry


class MemoryManager:
    """Manages persistent memory for a Mind — save, search, retrieve."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(self.storage_dir / ".memory.lock")

    def _mind_dir(self, mind_id: str, *, create: bool = False) -> Path:
        d = self.storage_dir / mind_id
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, entry: MemoryEntry) -> str:
        """Persist a memory entry. Returns the memory ID."""
        with self._lock.locked():
            mind_dir = self._mind_dir(entry.mind_id, create=True)
            filepath = mind_dir / f"{entry.id}.json"
            atomic_write_text(filepath, entry.model_dump_json(indent=2))
            return entry.id

    def retrieve(self, mind_id: str, memory_id: str) -> Optional[MemoryEntry]:
        """Load a specific memory by ID."""
        with self._lock.locked():
            filepath = self._mind_dir(mind_id) / f"{memory_id}.json"
            if not filepath.exists():
                return None
            data = json.loads(filepath.read_text())
            return MemoryEntry.model_validate(data)

    def search(self, mind_id: str, query: str, top_k: int = 10) -> list[MemoryEntry]:
        """Search memories by keyword overlap."""
        with self._lock.locked():
            mind_dir = self._mind_dir(mind_id)
            if not mind_dir.exists():
                return []

            query_tokens = _tokenize(query)
            if not query_tokens:
                return []

            scored: list[tuple[int, MemoryEntry]] = []
            for filepath in mind_dir.glob("*.json"):
                data = json.loads(filepath.read_text())
                entry = MemoryEntry.model_validate(data)
                entry_tokens = set(entry.relevance_keywords) | _tokenize(entry.content)
                overlap = len(query_tokens & entry_tokens)
                if overlap > 0:
                    scored.append((overlap, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:top_k]]

    def list_all(self, mind_id: str, category: Optional[str] = None) -> list[MemoryEntry]:
        """List all memories for a Mind, optionally filtered by category."""
        with self._lock.locked():
            mind_dir = self._mind_dir(mind_id)
            if not mind_dir.exists():
                return []

            entries: list[MemoryEntry] = []
            for filepath in sorted(mind_dir.glob("*.json")):
                data = json.loads(filepath.read_text())
                entry = MemoryEntry.model_validate(data)
                if category is None or entry.category == category:
                    entries.append(entry)
            return entries

    def delete(self, mind_id: str, memory_id: str) -> bool:
        """Delete a specific memory."""
        with self._lock.locked():
            filepath = self._mind_dir(mind_id) / f"{memory_id}.json"
            if filepath.exists():
                filepath.unlink()
                return True
            return False


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))
