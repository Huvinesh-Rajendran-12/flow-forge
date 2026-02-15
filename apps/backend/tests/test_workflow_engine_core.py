import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from backend.simulator import create_simulator
from backend.workflow.executor import WorkflowExecutor
from backend.workflow.schema import Workflow
from backend.workflow.store import WorkflowStore


class WorkflowEngineCoreTests(unittest.TestCase):
    def test_executor_resolves_global_and_upstream_parameters(self):
        workflow = Workflow.model_validate(
            {
                "id": "param-resolution",
                "name": "Parameter Resolution",
                "description": "Validates placeholder substitution",
                "team": "default",
                "nodes": [
                    {
                        "id": "create_hr_record",
                        "name": "Create HR",
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
                        "outputs": {"employee_id": "HR employee id"},
                    },
                    {
                        "id": "provision_google",
                        "name": "Provision Google",
                        "description": "Provision account",
                        "service": "google",
                        "action": "provision_account",
                        "actor": "it_admin",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "{{employee_name}}",
                                "description": "Employee full name",
                                "required": True,
                            }
                        ],
                        "depends_on": ["create_hr_record"],
                        "outputs": {"email": "Provisioned email"},
                    },
                    {
                        "id": "invite_slack",
                        "name": "Invite Slack",
                        "description": "Invite user by upstream email",
                        "service": "slack",
                        "action": "invite_user",
                        "actor": "it_admin",
                        "parameters": [
                            {
                                "name": "email",
                                "value": "{{provision_google.email}}",
                                "description": "Email from previous step",
                                "required": True,
                            },
                            {
                                "name": "channel_name",
                                "value": "#general",
                                "description": "Default channel",
                                "required": True,
                            },
                        ],
                        "depends_on": ["provision_google"],
                        "outputs": {},
                    },
                ],
                "edges": [
                    {"source": "create_hr_record", "target": "provision_google"},
                    {"source": "provision_google", "target": "invite_slack"},
                ],
                "parameters": {"employee_name": "Alice Chen"},
                "version": 1,
            }
        )

        state, trace, services, _ = create_simulator()
        executor = WorkflowExecutor(state=state, trace=trace, services=services)
        report = asyncio.run(executor.execute(workflow))

        self.assertEqual(report.failed, 0)
        self.assertEqual(report.successful, 3)

        slack_step = next(step for step in report.trace.steps if step.node_id == "invite_slack")
        self.assertEqual(slack_step.parameters["email"], "alice.chen@company.com")

    def test_executor_rejects_cyclic_workflows(self):
        cyclic = Workflow.model_validate(
            {
                "id": "cyclic",
                "name": "Cyclic Workflow",
                "description": "Contains a dependency cycle",
                "team": "default",
                "nodes": [
                    {
                        "id": "a",
                        "name": "Node A",
                        "description": "First node",
                        "service": "hr",
                        "action": "create_employee",
                        "actor": "hr_manager",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "Alice",
                                "description": "name",
                                "required": True,
                            }
                        ],
                        "depends_on": ["b"],
                        "outputs": {},
                    },
                    {
                        "id": "b",
                        "name": "Node B",
                        "description": "Second node",
                        "service": "google",
                        "action": "provision_account",
                        "actor": "it_admin",
                        "parameters": [
                            {
                                "name": "employee_name",
                                "value": "Alice",
                                "description": "name",
                                "required": True,
                            }
                        ],
                        "depends_on": ["a"],
                        "outputs": {},
                    },
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "a"},
                ],
                "parameters": {},
                "version": 1,
            }
        )

        state, trace, services, _ = create_simulator()
        executor = WorkflowExecutor(state=state, trace=trace, services=services)

        with self.assertRaises(ValueError):
            asyncio.run(executor.execute(cyclic))

    def test_workflow_store_versioned_json_format(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="flowforge-store-tests-"))
        store = WorkflowStore(temp_dir)

        try:
            wf_v1 = Workflow.model_validate(
                {
                    "id": "format-check",
                    "name": "Format Check",
                    "description": "Version 1",
                    "team": "default",
                    "nodes": [],
                    "edges": [],
                    "parameters": {},
                    "version": 1,
                }
            )
            wf_v2 = wf_v1.model_copy(update={"version": 2, "description": "Version 2"})

            store.save(wf_v1)
            store.save(wf_v2)

            latest = store.load("format-check", team="default")
            self.assertIsNotNone(latest)
            self.assertEqual(latest.version, 2)

            expected_file = temp_dir / "default" / "format-check-v2.json"
            self.assertTrue(expected_file.exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
