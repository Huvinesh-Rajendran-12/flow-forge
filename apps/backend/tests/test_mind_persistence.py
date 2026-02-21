import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.mind.database import init_db
from backend.mind.memory import MemoryManager
from backend.mind.schema import MemoryEntry, MindProfile, Task
from backend.mind.store import MindStore


class DatabaseInitTests(unittest.TestCase):
    def test_init_db_creates_tables_and_enables_wal(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="db-init-tests-"))
        try:
            db_path = tmp_dir / "test.db"
            conn = init_db(db_path)

            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode, "wal")

            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("minds", tables)
            self.assertIn("tasks", tables)
            self.assertIn("task_traces", tables)
            self.assertIn("memories", tables)

            conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_init_db_is_idempotent(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="db-idempotent-tests-"))
        try:
            db_path = tmp_dir / "test.db"
            conn1 = init_db(db_path)
            conn1.close()
            conn2 = init_db(db_path)
            conn2.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class MindStoreSqliteTests(unittest.TestCase):
    def test_mind_crud(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-store-tests-"))
        try:
            store = MindStore(tmp_dir / "test.db")

            mind = MindProfile(name="TestMind", personality="friendly")
            store.save_mind(mind)

            loaded = store.load_mind(mind.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.name, "TestMind")
            self.assertEqual(loaded.personality, "friendly")

            minds = store.list_minds()
            self.assertEqual(len(minds), 1)

            deleted = store.delete_mind(mind.id)
            self.assertTrue(deleted)
            self.assertIsNone(store.load_mind(mind.id))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_task_trace_roundtrip(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-trace-tests-"))
        try:
            store = MindStore(tmp_dir / "test.db")
            mind_id = "mind_1"
            task_id = "task_1"

            events = [{"type": "text", "content": "hello"}]
            store.save_task_trace(mind_id, task_id, events)

            trace = store.load_task_trace(mind_id, task_id)
            self.assertIsNotNone(trace)
            self.assertEqual(trace["task_id"], task_id)
            self.assertEqual(trace["events"], events)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_concurrent_writes(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-concurrent-tests-"))
        try:
            store = MindStore(tmp_dir / "test.db")
            mind_id = "mind_1"
            errors = []

            def worker(start: int) -> None:
                try:
                    for i in range(50):
                        task = Task(
                            id=f"task_{start}_{i}",
                            mind_id=mind_id,
                            description=f"task {start}_{i}",
                        )
                        store.save_task(mind_id, task)
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            tasks = store.list_tasks(mind_id)
            self.assertEqual(len(tasks), 200)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class MemoryFtsTests(unittest.TestCase):
    def test_fts_search_finds_matching_memories(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="memory-fts-tests-"))
        try:
            manager = MemoryManager(tmp_dir / "test.db")
            mind_id = "mind_1"

            manager.save(MemoryEntry(
                mind_id=mind_id,
                content="Release notes for version 3.2",
                category="notes",
                relevance_keywords=["release", "version"],
            ))
            manager.save(MemoryEntry(
                mind_id=mind_id,
                content="Meeting notes from Monday standup",
                category="notes",
                relevance_keywords=["meeting", "standup"],
            ))
            manager.save(MemoryEntry(
                mind_id=mind_id,
                content="Database migration plan for Q4",
                category="planning",
                relevance_keywords=["database", "migration"],
            ))

            results = manager.search(mind_id, "release notes")
            self.assertTrue(len(results) >= 1)
            self.assertTrue(any("release" in r.content.lower() for r in results))

            results = manager.search(mind_id, "standup meeting")
            self.assertTrue(len(results) >= 1)
            self.assertTrue(any("standup" in r.content.lower() for r in results))

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_search_empty_query_returns_empty(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="memory-empty-tests-"))
        try:
            manager = MemoryManager(tmp_dir / "test.db")
            results = manager.search("mind_1", "")
            self.assertEqual(results, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_search_isolates_by_mind_id(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="memory-isolation-tests-"))
        try:
            manager = MemoryManager(tmp_dir / "test.db")

            manager.save(MemoryEntry(
                mind_id="mind_a",
                content="Secret project alpha details",
            ))
            manager.save(MemoryEntry(
                mind_id="mind_b",
                content="Secret project beta details",
            ))

            results_a = manager.search("mind_a", "secret project")
            results_b = manager.search("mind_b", "secret project")

            self.assertEqual(len(results_a), 1)
            self.assertIn("alpha", results_a[0].content)
            self.assertEqual(len(results_b), 1)
            self.assertIn("beta", results_b[0].content)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_delete_removes_from_fts_index(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="memory-delete-tests-"))
        try:
            manager = MemoryManager(tmp_dir / "test.db")
            mind_id = "mind_1"

            entry = MemoryEntry(mind_id=mind_id, content="Unique searchable content")
            manager.save(entry)

            results = manager.search(mind_id, "unique searchable")
            self.assertEqual(len(results), 1)

            manager.delete(mind_id, entry.id)

            results = manager.search(mind_id, "unique searchable")
            self.assertEqual(len(results), 0)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
