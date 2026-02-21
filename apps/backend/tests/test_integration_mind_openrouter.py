import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.config import get_settings
from backend.mind.identity import create_mind_identity
from backend.mind.memory import MemoryManager
from backend.mind.pipeline import delegate_to_mind
from backend.mind.store import MindStore

MODEL_ID = "anthropic/claude-haiku-4.5"
MAX_ATTEMPTS = 2


class OpenRouterMindIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mind-openrouter-it-"))
        self.db_path = self.tmp_dir / "mind.db"
        self.mind_store = MindStore(self.db_path)
        self.memory_manager = MemoryManager(self.db_path)
        self._old_default_model = os.environ.get("DEFAULT_MODEL")

    async def asyncTearDown(self) -> None:
        if self._old_default_model is None:
            os.environ.pop("DEFAULT_MODEL", None)
        else:
            os.environ["DEFAULT_MODEL"] = self._old_default_model

        get_settings.cache_clear()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def _collect_events(
        self, mind_id: str, timeout_seconds: int = 240
    ) -> list[dict]:
        events: list[dict] = []

        async def _run() -> None:
            async for event in delegate_to_mind(
                mind_store=self.mind_store,
                memory_manager=self.memory_manager,
                mind_id=mind_id,
                description="Respond with one short sentence confirming the integration check.",
                team="default",
            ):
                events.append(event)

        await asyncio.wait_for(_run(), timeout=timeout_seconds)
        return events

    @staticmethod
    def _diagnostics(events: list[dict]) -> str:
        event_types = [event.get("type") for event in events]
        errors = [
            event.get("content") for event in events if event.get("type") == "error"
        ]
        tail = event_types[-12:]
        return f"types={event_types}; tail={tail}; errors={errors}"

    async def test_delegate_task_via_openrouter(self):
        if not os.environ.get("OPENROUTER_API_KEY"):
            self.skipTest("OPENROUTER_API_KEY is not set")
        if os.environ.get("RUN_OPENROUTER_INTEGRATION") != "1":
            self.skipTest(
                "Set RUN_OPENROUTER_INTEGRATION=1 to run external integration test"
            )

        os.environ.setdefault("ANTHROPIC_BASE_URL", "https://openrouter.ai/api/v1")
        os.environ["DEFAULT_MODEL"] = MODEL_ID
        get_settings.cache_clear()
        self.assertEqual(get_settings().default_model, MODEL_ID)

        mind = create_mind_identity(name="Integration Mind", personality="concise")
        self.mind_store.save_mind(mind)

        last_events: list[dict] = []
        for _ in range(MAX_ATTEMPTS):
            last_events = await self._collect_events(mind.id)
            finished = next(
                (
                    event
                    for event in last_events
                    if event.get("type") == "task_finished"
                ),
                None,
            )
            if finished and finished.get("content", {}).get("status") == "completed":
                break

        event_types = [event.get("type") for event in last_events]
        self.assertIn(
            "task_started",
            event_types,
            "Expected task_started event from delegation pipeline. "
            + self._diagnostics(last_events),
        )
        self.assertIn(
            "task_finished",
            event_types,
            "Expected task_finished event from delegation pipeline. "
            + self._diagnostics(last_events),
        )

        finished = next(
            event for event in last_events if event.get("type") == "task_finished"
        )
        self.assertEqual(
            finished["content"].get("status"),
            "completed",
            "Expected completed status for Mind delegation run. "
            + self._diagnostics(last_events),
        )
        self.assertTrue(
            any(
                event_type in {"text", "result", "tool_use", "tool_result"}
                for event_type in event_types
            ),
            "Expected streamed reasoning/tool events from agent run. "
            + self._diagnostics(last_events),
        )

        tasks = self.mind_store.list_tasks(mind.id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, "completed")

        trace = self.mind_store.load_task_trace(mind.id, tasks[0].id)
        self.assertIsNotNone(trace)
        self.assertGreater(len(trace.get("events", [])), 0)
