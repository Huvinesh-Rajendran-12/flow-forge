import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend import main
from backend.mind.memory import MemoryManager
from backend.mind.schema import Task
from backend.mind.store import MindStore
from backend.mind.tools.primitives import create_memory_tools, create_spawn_agent_tool


class MindApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mind-api-tests-"))
        self._old_mind_store = main.mind_store
        self._old_memory_manager = main.memory_manager

        db_path = self.tmp_dir / "test.db"
        main.mind_store = MindStore(db_path)
        main.memory_manager = MemoryManager(db_path)
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

        list_resp = self.client.get("/api/minds")
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(any(m["id"] == mind_id for m in list_resp.json()))

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
            yield {
                "type": "text",
                "content": "Done: drafted a concise release note summary.",
            }
            yield {"type": "result", "content": {"subtype": "completed"}}

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Summarize release notes", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        event_types = [evt["type"] for evt in events]
        self.assertIn("task_started", event_types)
        self.assertIn("memory_context", event_types)
        self.assertIn("tool_registry", event_types)
        self.assertIn("tool_use", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("result", event_types)
        self.assertIn("memory_saved", event_types)
        self.assertIn("task_finished", event_types)

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        self.assertEqual(tasks_resp.status_code, 200)
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "completed")

        task_id = tasks[0]["id"]
        trace_resp = self.client.get(f"/api/minds/{mind_id}/tasks/{task_id}/trace")
        self.assertEqual(trace_resp.status_code, 200)
        trace = trace_resp.json()
        self.assertEqual(trace["task_id"], task_id)
        trace_types = [evt["type"] for evt in trace["events"]]
        self.assertIn("task_started", trace_types)
        self.assertIn("tool_use", trace_types)
        self.assertIn("task_finished", trace_types)

        memory_resp = self.client.get(f"/api/minds/{mind_id}/memory")
        self.assertEqual(memory_resp.status_code, 200)
        memories = memory_resp.json()
        self.assertTrue(any(m["category"] == "task_result" for m in memories))

    def test_spawn_agent_uses_isolated_workspace(self):
        create_resp = self.client.post("/api/minds", json={"name": "Hub"})
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            prompt = kwargs.get("prompt", "")
            tools_override = kwargs.get("tools_override") or []
            tools = {tool.name: tool for tool in tools_override}

            if prompt.startswith("[Drone Objective]"):
                # This write must stay inside the drone workspace.
                await tools["write_file"].execute(
                    "drone_write",
                    {"path": "artifact.txt", "content": "from drone"},
                )
                yield {"type": "text", "content": "drone complete"}
                yield {"type": "result", "content": {"subtype": "completed"}}
                return

            await tools["spawn_agent"].execute(
                "parent_spawn",
                {"objective": "create artifact", "max_turns": 5},
            )

            leak_detected = False
            try:
                read_result = await tools["read_file"].execute(
                    "parent_read", {"path": "artifact.txt"}
                )
                leak_detected = "from drone" in read_result.content[0].text
            except Exception:
                leak_detected = False

            yield {"type": "text", "content": f"drone_workspace_leak={leak_detected}"}
            yield {"type": "result", "content": {"subtype": "completed"}}

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={
                    "description": "Run workspace isolation check",
                    "team": "default",
                },
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        text_events = [e.get("content") for e in events if e.get("type") == "text"]
        self.assertTrue(
            any("drone_workspace_leak=False" in str(content) for content in text_events)
        )

    def test_result_final_text_is_persisted_and_saved_to_memory(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Signal"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "Completed summary from final result payload.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Summarize launch plan", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        event_types = [evt["type"] for evt in events]
        self.assertIn("memory_context", event_types)
        self.assertIn("memory_saved", event_types)

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(
            tasks[0]["result"], "Completed summary from final result payload."
        )

        memory_resp = self.client.get(f"/api/minds/{mind_id}/memory")
        memories = memory_resp.json()
        categories = {memory["category"] for memory in memories}
        self.assertIn("task_result", categories)
        self.assertIn("mind_insight", categories)

        task_result_memory = next(
            memory for memory in memories if memory["category"] == "task_result"
        )
        self.assertIn(
            "Completed summary from final result payload.",
            task_result_memory["content"],
        )

    def test_error_result_marks_task_failed(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Signal"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            yield {
                "type": "result",
                "content": {
                    "subtype": "error",
                    "error_message": "Upstream provider unavailable",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Run failure check", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        event_types = [evt["type"] for evt in events]
        self.assertIn("error", event_types)

        finished = next(evt for evt in events if evt["type"] == "task_finished")
        self.assertEqual(finished["content"]["status"], "failed")

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "failed")
        self.assertIn("Upstream provider unavailable", tasks[0]["result"])

    def test_intermediate_error_event_does_not_force_failure_when_result_completes(
        self,
    ):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Signal"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            yield {"type": "error", "content": "Transient tool timeout"}
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "Recovered and completed successfully.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Run recovery check", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        event_types = [evt["type"] for evt in events]
        self.assertIn("error", event_types)

        finished = next(evt for evt in events if evt["type"] == "task_finished")
        self.assertEqual(finished["content"]["status"], "completed")

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["result"], "Recovered and completed successfully.")

    def test_text_delta_volume_does_not_trip_structural_event_limit(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Signal"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        async def fake_run_agent(*args, **kwargs):
            for _ in range(350):
                yield {"type": "text_delta", "content": "x"}
            yield {
                "type": "text",
                "content": "I suggest adding a charter editor and capability roadmap.",
            }
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "I suggest adding a charter editor and capability roadmap.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "How should you evolve next?", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                events = self._read_sse(response)

        finished = next(evt for evt in events if evt["type"] == "task_finished")
        self.assertEqual(finished["content"]["status"], "completed")

        error_messages = [
            str(evt.get("content")) for evt in events if evt.get("type") == "error"
        ]
        self.assertFalse(
            any("Event limit reached" in message for message in error_messages),
            msg=f"Unexpected structural event limit failure: {error_messages}",
        )

        tasks_resp = self.client.get(f"/api/minds/{mind_id}/tasks")
        tasks = tasks_resp.json()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertIn("charter editor", tasks[0]["result"])

    def test_create_mind_includes_default_charter_and_accepts_override(self):
        default_resp = self.client.post(
            "/api/minds",
            json={"name": "Atlas"},
        )
        self.assertEqual(default_resp.status_code, 200)
        default_mind = default_resp.json()
        self.assertIn("charter", default_mind)
        self.assertIn("mission", default_mind["charter"])
        self.assertIn("reason_for_existence", default_mind["charter"])
        self.assertTrue(default_mind["charter"]["operating_principles"])

        custom_resp = self.client.post(
            "/api/minds",
            json={
                "name": "Navigator",
                "charter": {
                    "mission": "Design and evolve the Mind platform with the user.",
                    "non_goals": ["Shipping capability changes without user consent."],
                },
            },
        )
        self.assertEqual(custom_resp.status_code, 200)
        custom_mind = custom_resp.json()
        self.assertEqual(
            custom_mind["charter"]["mission"],
            "Design and evolve the Mind platform with the user.",
        )
        self.assertIn(
            "Shipping capability changes without user consent.",
            custom_mind["charter"]["non_goals"],
        )
        self.assertTrue(custom_mind["charter"]["reason_for_existence"])

    def test_patch_mind_updates_profile_and_charter_fields(self):
        create_resp = self.client.post(
            "/api/minds",
            json={
                "name": "Atlas",
                "personality": "calm",
                "preferences": {"tone": "direct"},
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        original = create_resp.json()
        mind_id = original["id"]

        patch_resp = self.client.patch(
            f"/api/minds/{mind_id}",
            json={
                "name": "Atlas Prime",
                "personality": "critical friend",
                "preferences": {"tone": "analytical", "depth": "deep"},
                "system_prompt": "Challenge assumptions and stay explicit.",
                "charter": {
                    "mission": "Continuously evaluate and improve Mind fitness.",
                    "reflection_focus": [
                        "Assess current capability limits.",
                        "Recommend next capability upgrades.",
                    ],
                },
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        patched = patch_resp.json()

        self.assertEqual(patched["name"], "Atlas Prime")
        self.assertEqual(patched["personality"], "critical friend")
        self.assertEqual(
            patched["preferences"],
            {"tone": "analytical", "depth": "deep"},
        )
        self.assertEqual(
            patched["system_prompt"],
            "Challenge assumptions and stay explicit.",
        )
        self.assertEqual(
            patched["charter"]["mission"],
            "Continuously evaluate and improve Mind fitness.",
        )
        self.assertEqual(
            patched["charter"]["reflection_focus"],
            [
                "Assess current capability limits.",
                "Recommend next capability upgrades.",
            ],
        )
        self.assertEqual(
            patched["charter"]["reason_for_existence"],
            original["charter"]["reason_for_existence"],
        )

        get_resp = self.client.get(f"/api/minds/{mind_id}")
        self.assertEqual(get_resp.status_code, 200)
        loaded = get_resp.json()
        self.assertEqual(loaded["name"], "Atlas Prime")
        self.assertEqual(
            loaded["charter"]["mission"],
            "Continuously evaluate and improve Mind fitness.",
        )

        implicit_resp = self.client.get(
            f"/api/minds/{mind_id}/memory?category=implicit_feedback"
        )
        self.assertEqual(implicit_resp.status_code, 200)
        implicit_memories = implicit_resp.json()
        self.assertTrue(implicit_memories)
        self.assertIn("profile update", implicit_memories[-1]["content"].lower())
        self.assertIn("preferences_update", implicit_memories[-1]["relevance_keywords"])

    def test_patch_mind_returns_404_for_unknown_mind(self):
        patch_resp = self.client.patch(
            "/api/minds/does_not_exist",
            json={"personality": "updated"},
        )
        self.assertEqual(patch_resp.status_code, 404)
        self.assertEqual(patch_resp.json()["detail"], "Mind not found")

    def test_add_feedback_persists_memory(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Coach"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        feedback_resp = self.client.post(
            f"/api/minds/{mind_id}/feedback",
            json={
                "content": "Default to acting on reversible ambiguity; ask only for high-risk moves.",
                "rating": 5,
                "tags": ["autonomy", "risk_tolerance"],
            },
        )
        self.assertEqual(feedback_resp.status_code, 200)
        saved_feedback = feedback_resp.json()
        self.assertEqual(saved_feedback["category"], "user_feedback")
        self.assertIn("autonomy", saved_feedback["relevance_keywords"])

        memory_resp = self.client.get(f"/api/minds/{mind_id}/memory")
        memories = memory_resp.json()
        self.assertTrue(
            any(memory["category"] == "user_feedback" for memory in memories)
        )

    def test_delegate_prompt_includes_recent_user_feedback_memory(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Coach"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        feedback_resp = self.client.post(
            f"/api/minds/{mind_id}/feedback",
            json={
                "content": "Prefer shipping a reversible draft over asking for confirmation.",
                "tags": ["shipping_style"],
            },
        )
        self.assertEqual(feedback_resp.status_code, 200)

        captured_prompt: dict[str, str] = {}

        async def fake_run_agent(*args, **kwargs):
            captured_prompt["value"] = kwargs.get("system_prompt", "")
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "Applied feedback-aware recommendation.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "Plan next sprint priorities", "team": "default"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                _ = self._read_sse(response)

        system_prompt = captured_prompt.get("value", "")
        self.assertIn("Prefer shipping a reversible draft", system_prompt)
        self.assertIn("user_feedback", system_prompt)

    def test_quick_followup_does_not_infer_implicit_feedback(self):
        create_resp = self.client.post(
            "/api/minds",
            json={"name": "Scout"},
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        captured_prompts: list[str] = []

        async def fake_run_agent(*args, **kwargs):
            captured_prompts.append(kwargs.get("system_prompt", ""))
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "Delivered concise plan draft.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={
                    "description": "Draft onboarding plan for backend engineers",
                    "team": "default",
                },
            ) as first_response:
                self.assertEqual(first_response.status_code, 200)
                _ = self._read_sse(first_response)

            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={
                    "description": "Revise onboarding plan for backend engineers with clearer phases",
                    "team": "default",
                },
            ) as second_response:
                self.assertEqual(second_response.status_code, 200)
                second_events = self._read_sse(second_response)

        self.assertGreaterEqual(len(captured_prompts), 2)
        second_prompt = captured_prompts[-1]
        self.assertNotIn("quick follow-up on a similar task", second_prompt)

        memory_context_event = next(
            event for event in second_events if event["type"] == "memory_context"
        )
        context_payload = memory_context_event["content"]
        self.assertEqual(context_payload.get("implicit_count", 0), 0)

        implicit_resp = self.client.get(
            f"/api/minds/{mind_id}/memory?category=implicit_feedback"
        )
        self.assertEqual(implicit_resp.status_code, 200)
        implicit_memories = implicit_resp.json()
        self.assertEqual(implicit_memories, [])

    def test_delegate_prompt_includes_charter_and_runtime_manifest(self):
        create_resp = self.client.post(
            "/api/minds",
            json={
                "name": "Builder",
                "charter": {
                    "mission": "Continuously assess and improve Mind capabilities.",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        mind_id = create_resp.json()["id"]

        captured_prompt: dict[str, str] = {}

        async def fake_run_agent(*args, **kwargs):
            captured_prompt["value"] = kwargs.get("system_prompt", "")
            yield {
                "type": "result",
                "content": {
                    "subtype": "completed",
                    "final_text": "Capability self-assessment complete.",
                },
            }

        with patch("backend.mind.pipeline.run_agent", new=fake_run_agent):
            with self.client.stream(
                "POST",
                f"/api/minds/{mind_id}/delegate",
                json={"description": "What capabilities should we add next?"},
            ) as response:
                self.assertEqual(response.status_code, 200)
                _ = self._read_sse(response)

        system_prompt = captured_prompt.get("value", "")
        self.assertIn("Mind charter:", system_prompt)
        self.assertIn(
            "Continuously assess and improve Mind capabilities.",
            system_prompt,
        )
        self.assertIn("Runtime capability manifest:", system_prompt)
        self.assertIn("Tools available in this run:", system_prompt)
        self.assertIn("spawn_agent_max_calls", system_prompt)
        self.assertIn("stream_event_limit", system_prompt)
        self.assertIn("text_delta_event_limit", system_prompt)
        self.assertIn("Meta conversation policy:", system_prompt)


class MindStoreTests(unittest.TestCase):
    def test_list_tasks_orders_by_created_at_desc(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="mind-store-tests-"))
        store = MindStore(tmp_dir / "test.db")
        try:
            mind_id = "mind_1"
            older = Task(
                id="zzz_older",
                mind_id=mind_id,
                description="older task",
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            newer = Task(
                id="aaa_newer",
                mind_id=mind_id,
                description="newer task",
                created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            )

            store.save_task(mind_id, older)
            store.save_task(mind_id, newer)

            tasks = store.list_tasks(mind_id)
            self.assertEqual([task.id for task in tasks], ["aaa_newer", "zzz_older"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class SpawnAgentToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_spawn_agent_limits_calls_and_turns(self):
        calls: list[tuple[str, int]] = []

        async def fake_spawn(objective: str, max_turns: int) -> str:
            calls.append((objective, max_turns))
            return f"ok:{objective}:{max_turns}"

        tool = create_spawn_agent_tool(fake_spawn, max_calls=1, max_turns_cap=7)

        first = await tool.execute(
            "tc_1", {"objective": "Research pricing", "max_turns": 99}
        )
        first_text = getattr(first.content[0], "text", "")
        self.assertIn("ok:Research pricing:7", first_text)

        second = await tool.execute(
            "tc_2", {"objective": "Write draft", "max_turns": 2}
        )
        second_text = getattr(second.content[0], "text", "")
        self.assertIn("call limit reached", second_text)

        self.assertEqual(calls, [("Research pricing", 7)])


class MemoryToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_save_limits_calls(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="memory-tool-tests-"))
        manager = MemoryManager(tmp_dir / "test.db")
        try:
            tools = create_memory_tools(manager, "mind_1", max_saves=1)
            memory_save = next(tool for tool in tools if tool.name == "memory_save")

            first = await memory_save.execute("mc_1", {"content": "first note"})
            self.assertIn("Saved memory:", getattr(first.content[0], "text", ""))

            second = await memory_save.execute("mc_2", {"content": "second note"})
            self.assertIn(
                "call limit reached",
                getattr(second.content[0], "text", ""),
            )

            memories = manager.list_all("mind_1")
            self.assertEqual(len(memories), 1)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
