import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.agents.workflow_agent import generate_workflow
from backend.workflow.schema import Workflow
from backend.workflow.store import WorkflowStore


class WorkflowGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="flowforge-tests-"))
        self.store = WorkflowStore(self.tmp_dir)

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def _collect_messages(self, agen):
        messages = []
        async for message in agen:
            messages.append(message)
        return messages

    async def test_generates_valid_workflow_json_and_saves_it(self):
        async def fake_run_agent(prompt, system_prompt, workspace_dir, team, allowed_tools=None, max_turns=50):
            workflow = {
                "id": "day1-onboarding",
                "name": "Day 1 Onboarding",
                "description": "Provision core accounts for a new hire",
                "team": team,
                "nodes": [
                    {
                        "id": "create_hr_record",
                        "name": "Create HR Record",
                        "description": "Create employee in HR",
                        "service": "hr",
                        "action": "create_employee",
                        "actor": "hr_manager",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "{{employee_name}}",
                                "description": "Employee full name",
                                "required": True,
                            },
                            {
                                "name": "role",
                                "value": "{{role}}",
                                "description": "Role",
                                "required": True,
                            },
                        ],
                        "depends_on": [],
                        "outputs": {"employee_id": "HR employee id"},
                    },
                    {
                        "id": "provision_google",
                        "name": "Provision Google",
                        "description": "Provision Google Workspace account",
                        "service": "google",
                        "action": "provision_account",
                        "actor": "it_admin",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "{{employee_name}}",
                                "description": "Employee name",
                                "required": True,
                            }
                        ],
                        "depends_on": ["create_hr_record"],
                        "outputs": {"email": "Provisioned email"},
                    },
                ],
                "edges": [
                    {"source": "create_hr_record", "target": "provision_google"}
                ],
                "parameters": {"employee_name": "Alice Chen", "role": "Engineer"},
                "version": 1,
            }

            Path(workspace_dir, "workflow.json").write_text(json.dumps(workflow, indent=2))
            yield {"type": "text", "content": "workflow drafted"}

        with patch("backend.agents.workflow_agent.run_agent", new=fake_run_agent):
            messages = await self._collect_messages(
                generate_workflow(
                    description="Create onboarding workflow",
                    context={"employee_name": "Alice Chen", "role": "Engineer"},
                    workflow_store=self.store,
                )
            )

        types = [m["type"] for m in messages]
        self.assertIn("workflow", types)
        self.assertIn("execution_report", types)
        self.assertIn("workflow_saved", types)

        workflow_payload = next(m["content"] for m in messages if m["type"] == "workflow")
        validated = Workflow.model_validate(workflow_payload)
        self.assertEqual(validated.id, "day1-onboarding")
        self.assertEqual(validated.version, 1)

        report_payload = next(m["content"]["report"] for m in messages if m["type"] == "execution_report")
        self.assertEqual(report_payload["failed"], 0)

        saved = self.store.load("day1-onboarding", team="default")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.version, 1)

    async def test_self_correction_loop_fixes_failed_workflow(self):
        calls = {"count": 0}

        broken = {
            "id": "self-correct-workflow",
            "name": "Broken Then Fixed",
            "description": "Intentionally broken workflow to trigger self-correction",
            "team": "default",
            "nodes": [
                {
                    "id": "create_hr_record",
                    "name": "Create HR Record",
                    "description": "Create employee in HR",
                    "service": "hr",
                    "action": "create_employee",
                    "actor": "hr_manager",
                    "parameters": [
                        {
                            "name": "employee_name",
                            "value": "{{employee_name}}",
                            "description": "Employee full name",
                            "required": True,
                        }
                    ],
                    "depends_on": [],
                    "outputs": {"employee_id": "HR employee id"},
                },
                {
                    "id": "invite_slack",
                    "name": "Invite Slack Early",
                    "description": "Invites before Google provisioning (broken)",
                    "service": "slack",
                    "action": "invite_user",
                    "actor": "it_admin",
                    "parameters": [
                        {
                            "name": "email",
                            "value": "{{provision_google.email}}",
                            "description": "Email from google output",
                            "required": True,
                        }
                    ],
                    "depends_on": ["create_hr_record"],
                    "outputs": {},
                },
                {
                    "id": "provision_google",
                    "name": "Provision Google",
                    "description": "Provision Google account",
                    "service": "google",
                    "action": "provision_account",
                    "actor": "it_admin",
                    "parameters": [
                        {
                            "name": "employee_name",
                            "value": "{{employee_name}}",
                            "description": "Employee name",
                            "required": True,
                        }
                    ],
                    "depends_on": ["create_hr_record"],
                    "outputs": {"email": "Provisioned email"},
                },
            ],
            "edges": [
                {"source": "create_hr_record", "target": "invite_slack"},
                {"source": "create_hr_record", "target": "provision_google"},
            ],
            "parameters": {"employee_name": "Alice Chen"},
            "version": 1,
        }

        fixed = {
            "id": "self-correct-workflow",
            "name": "Broken Then Fixed",
            "description": "Corrected workflow",
            "team": "default",
            "nodes": [
                broken["nodes"][0],
                broken["nodes"][2],
                {
                    **broken["nodes"][1],
                    "depends_on": ["provision_google"],
                },
            ],
            "edges": [
                {"source": "create_hr_record", "target": "provision_google"},
                {"source": "provision_google", "target": "invite_slack"},
            ],
            "parameters": {"employee_name": "Alice Chen"},
            "version": 1,
        }

        async def fake_run_agent(prompt, system_prompt, workspace_dir, team, allowed_tools=None, max_turns=50):
            calls["count"] += 1
            target = Path(workspace_dir, "workflow.json")

            if "was executed but had failures" in prompt:
                target.write_text(json.dumps(fixed, indent=2))
                yield {"type": "text", "content": "applied correction"}
            else:
                target.write_text(json.dumps(broken, indent=2))
                yield {"type": "text", "content": "drafted initial workflow"}

        with patch("backend.agents.workflow_agent.run_agent", new=fake_run_agent):
            messages = await self._collect_messages(
                generate_workflow(
                    description="Create onboarding workflow",
                    context={"employee_name": "Alice Chen"},
                    workflow_store=self.store,
                )
            )

        reports = [m["content"] for m in messages if m["type"] == "execution_report"]
        attempts = [r["attempt"] for r in reports]
        self.assertEqual(attempts, [1, 2])

        self.assertGreaterEqual(calls["count"], 2)
        self.assertTrue(any(m["type"] == "text" and "self-correction" in m["content"] for m in messages))

        final_report = reports[-1]["report"]
        self.assertEqual(final_report["failed"], 0)

    async def test_multi_turn_refinement_updates_existing_workflow(self):
        existing = Workflow.model_validate(
            {
                "id": "onboarding-refine",
                "name": "Onboarding",
                "description": "Initial workflow",
                "team": "default",
                "nodes": [
                    {
                        "id": "create_hr_record",
                        "name": "Create HR Record",
                        "description": "Create employee",
                        "service": "hr",
                        "action": "create_employee",
                        "actor": "hr_manager",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "{{employee_name}}",
                                "description": "Employee full name",
                                "required": True,
                            }
                        ],
                        "depends_on": [],
                        "outputs": {},
                    }
                ],
                "edges": [],
                "parameters": {"employee_name": "Alice Chen"},
                "version": 1,
            }
        )

        seen_modify_prompt = {"value": False}

        async def fake_run_agent(prompt, system_prompt, workspace_dir, team, allowed_tools=None, max_turns=50):
            if "Modify the existing workflow" in prompt:
                seen_modify_prompt["value"] = True

            refined = {
                "id": "onboarding-refine",
                "name": "Onboarding Refined",
                "description": "Refined with an extra provisioning step",
                "team": "default",
                "nodes": [
                    existing.nodes[0].model_dump(),
                    {
                        "id": "provision_google",
                        "name": "Provision Google",
                        "description": "Provision Google account",
                        "service": "google",
                        "action": "provision_account",
                        "actor": "it_admin",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "{{employee_name}}",
                                "description": "Employee name",
                                "required": True,
                            }
                        ],
                        "depends_on": ["create_hr_record"],
                        "outputs": {"email": "Provisioned email"},
                    },
                ],
                "edges": [
                    {"source": "create_hr_record", "target": "provision_google"}
                ],
                "parameters": {"employee_name": "Alice Chen"},
                "version": 2,
            }
            Path(workspace_dir, "workflow.json").write_text(json.dumps(refined, indent=2))
            yield {"type": "text", "content": "workflow refined"}

        with patch("backend.agents.workflow_agent.run_agent", new=fake_run_agent):
            messages = await self._collect_messages(
                generate_workflow(
                    description="Add Google provisioning to this workflow",
                    context={"employee_name": "Alice Chen"},
                    existing_workflow=existing,
                    workflow_store=self.store,
                )
            )

        self.assertTrue(seen_modify_prompt["value"])

        workflow_payload = [m["content"] for m in messages if m["type"] == "workflow"][-1]
        self.assertEqual(workflow_payload["version"], 2)
        self.assertTrue(any(node["id"] == "provision_google" for node in workflow_payload["nodes"]))
