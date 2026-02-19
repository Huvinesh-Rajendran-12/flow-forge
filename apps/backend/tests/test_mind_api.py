import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend import main
from backend.mind.memory import MemoryManager
from backend.mind.store import MindStore
from backend.mind.tools.primitives import create_spawn_agent_tool


class MindApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mind-api-tests-"))
        self._old_mind_store = main.mind_store
        self._old_memory_manager = main.memory_manager

        main.mind_store = MindStore(self.tmp_dir)
        main.memory_manager = MemoryManager(self.tmp_dir / "memory")
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.mind_store = self._old_mind_store
        main.memory_manager = self._old_memory_manager
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @staticmethod
    def _read_sse(response) -> list[dict]:
        payload = ""
        for chunk in response.iter_text():
            payload += chunk

        decoder = json.JSONDecoder()
        events: list[dict] = []

        for line in payload.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue

            data = line[6:].strip()
            idx = 0
            while idx < len(data):
                while idx < len(data) and data[idx].isspace():
                    idx += 1
                if idx >= len(data):
                    break
                obj, next_idx = decoder.raw_decode(data, idx)
                events.append(obj)
                idx = next_idx

        return events

    def test_create_mind_delegate_and_persist_task_memory(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Hub", "personality": "helpful"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            tools_override = kwargs.get("tools_override") or []
            tool_names = {tool.name for tool in tools_override}
            assert "spawn_agent" in tool_names
            assert "memory_search" in tool_names

            yield {
                "type": "tool_use",
                "content": {
                    "tool": "memory_search",
                    "input": {"query": "release notes"},
                    "id": "tu_1",
                },
            }
            yield {
                "type": "tool_result",
                "content": {
                    "tool_use_id": "tu_1",
                    "result": "[]",
                    "is_error": False,
                },
            }
            yield {"type": "text", "content": "Done: drafted a concise release note summary."}
            yield {"type": "result", "content": {"subtype": "completed"}}

        with patch("backend.mind.reasoning.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Summarize release notes", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        event_types = [evt["type"] for evt in events]
        self.assertIn("tool_registry", event_types)
        self.assertIn("tool_use", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("result", event_types)

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        self.assertEqual(tasks_resp.status_code, 200)
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "completed")

        memory_resp = self.client.get(f"/api/minds/{mind_id}/memory")
        self.assertEqual(memory_resp.status_code, 200)
        memories = memory_resp.json()
        self.assertTrue(any(m["category"] == "task_result" for m in memories))


class SpawnAgentToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_spawn_agent_limits_calls_and_turns(self):
        calls: list[tuple[str, int]] = []

        async def fake_spawn(objective: str, max_turns: int) -> str:
            calls.append((objective, max_turns))
            return f"ok:{objective}:{max_turns}"

        tool = create_spawn_agent_tool(fake_spawn, max_calls=1, max_turns_cap=7)

        first = await tool.execute("tc_1", {"objective": "Research pricing", "max_turns": 99})
        first_text = first.content[0].text
        self.assertIn("ok:Research pricing:7", first_text)

        second = await tool.execute("tc_2", {"objective": "Write draft", "max_turns": 2})
        second_text = second.content[0].text
        self.assertIn("call limit reached", second_text)

        self.assertEqual(calls, [("Research pricing", 7)])
