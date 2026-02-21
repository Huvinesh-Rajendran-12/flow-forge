import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.mind.persistence import FileLock, atomic_write_text


class MindPersistenceTests(unittest.TestCase):
    def test_atomic_write_text_replaces_content(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-persistence-tests-"))
        try:
            path = tmp_dir / "state.json"
            atomic_write_text(path, json.dumps({"value": 1}))
            atomic_write_text(path, json.dumps({"value": 2}))

            data = json.loads(path.read_text())
            self.assertEqual(data["value"], 2)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_file_lock_guards_critical_section_across_threads(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-persistence-lock-tests-"))
        try:
            lock = FileLock(tmp_dir / ".state.lock")
            counter = {"value": 0}

            def worker() -> None:
                for _ in range(150):
                    with lock.locked():
                        current = counter["value"]
                        time.sleep(0.0001)
                        counter["value"] = current + 1

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(counter["value"], 600)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
