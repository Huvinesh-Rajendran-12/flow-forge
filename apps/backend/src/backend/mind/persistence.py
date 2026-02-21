"""Persistence helpers for Mind storage with atomic writes and simple file locks."""

from __future__ import annotations

import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - platform-dependent import
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically write text content to a file using replace-on-commit."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


class FileLock:
    """Simple process/thread-safe file lock using flock when available."""

    def __init__(self, path: Path):
        self.path = path
        self._thread_lock = threading.RLock()

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Acquire an exclusive lock and release it on exit."""
        with self._thread_lock:
            with self.path.open("a+", encoding="utf-8") as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
