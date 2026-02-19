import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.workflow.pipeline import generate_workflow
from backend.config import get_settings
from backend.workflow.schema import Workflow
from backend.workflow.store import WorkflowStore

MODEL_ID = "anthropic/claude-haiku-4.5"
MAX_ATTEMPTS = 3


class OpenRouterIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="flowforge-openrouter-it-"))
        self.store = WorkflowStore(self.tmp_dir)
        self._old_default_model = os.environ.get("DEFAULT_MODEL")

    async def asyncTearDown(self) -> None:
        if self._old_default_model is None:
            os.environ.pop("DEFAULT_MODEL", None)
        else:
            os.environ["DEFAULT_MODEL"] = self._old_default_model

        get_settings.cache_clear()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def _collect_messages(self, timeout_seconds: int = 240):
        messages = []

        async def _run():
            async for msg in generate_workflow(
                description=(
                    "Create a minimal Day 1 onboarding workflow with exactly two steps: "
                    "(1) create HR employee record, "
                    "(2) provision Google account after HR record. "
                    "Do not add extra optional steps."
                ),
                context={
                    "employee_name": "Integration Test User",
                    "role": "Software Engineer",
                },
                workflow_store=self.store,
            ):
                messages.append(msg)

        await asyncio.wait_for(_run(), timeout=timeout_seconds)
        return messages

    @staticmethod
    def _diagnostics(messages: list[dict]) -> str:
        msg_types = [m.get("type") for m in messages]
        errors = [m.get("content") for m in messages if m.get("type") == "error"]
        tail = msg_types[-12:]
        return f"types={msg_types}; tail={tail}; errors={errors}"

    async def test_generate_workflow_via_openrouter(self):
        if not os.environ.get("OPENROUTER_API_KEY"):
            self.skipTest("OPENROUTER_API_KEY is not set")
        if os.environ.get("RUN_OPENROUTER_INTEGRATION") != "1":
            self.skipTest("Set RUN_OPENROUTER_INTEGRATION=1 to run external integration test")

        # OpenRouter Anthropic-compatible endpoint.
        os.environ.setdefault("ANTHROPIC_BASE_URL", "https://openrouter.ai/api/v1")

        # Force model for this integration run.
        os.environ["DEFAULT_MODEL"] = MODEL_ID
        get_settings.cache_clear()
        self.assertEqual(get_settings().default_model, MODEL_ID)

        last_messages: list[dict] = []
        for _ in range(MAX_ATTEMPTS):
            last_messages = await self._collect_messages(timeout_seconds=300)
            msg_types = [m.get("type") for m in last_messages]
            if "workflow" in msg_types and "execution_report" in msg_types:
                break

        msg_types = [m.get("type") for m in last_messages]
        self.assertIn(
            "workflow",
            msg_types,
            "Expected a workflow message from generator. " + self._diagnostics(last_messages),
        )
        self.assertIn(
            "execution_report",
            msg_types,
            "Expected an execution report from simulator. " + self._diagnostics(last_messages),
        )

        workflow_payload = next(m["content"] for m in last_messages if m["type"] == "workflow")
        workflow = Workflow.model_validate(workflow_payload)
        self.assertGreaterEqual(len(workflow.nodes), 2)

        report_payload = next(m["content"]["report"] for m in last_messages if m["type"] == "execution_report")
        self.assertEqual(
            report_payload["failed"],
            0,
            f"Workflow execution failed: {report_payload}. {self._diagnostics(last_messages)}",
        )

        saved = self.store.load(workflow.id, team=workflow.team)
        self.assertIsNotNone(saved, "Expected generated workflow to be persisted")
