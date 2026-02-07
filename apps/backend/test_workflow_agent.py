#!/usr/bin/env python3
"""Test script for the FlowForge workflow engine.

Tests:
1. Schema validation — build a workflow by hand and round-trip it
2. Simulator — run services in correct/wrong order, failure injection
3. Executor — build a small DAG, execute, verify topological ordering
4. Executor with failure injection — verify cascading skips
5. API catalog search — verify search returns correct services
6. KB search — verify search returns correct KB sections
7. MCP server creation — verify factory returns valid config
8. Workflow save — verify save+load roundtrip via WorkflowStore
9. Agent generation — full end-to-end: agent produces workflow.json, executor runs it
"""
import asyncio
import tempfile
from pathlib import Path

from backend.simulator import create_simulator
from backend.simulator.failures import FailureConfig, FailureRule
from backend.simulator.services import ServiceError
from backend.simulator.state import ExecutionTrace, SimulatorState
from backend.workflow.executor import WorkflowExecutor
from backend.workflow.schema import NodeParameter, Workflow, WorkflowEdge, WorkflowNode
from backend.workflow.store import WorkflowStore


# ---------------------------------------------------------------------------
# Test 1: Schema validation
# ---------------------------------------------------------------------------


def test_schema_validation():
    """Create a workflow JSON by hand, parse it, confirm it round-trips."""
    print("Test 1: Schema Validation")
    print("-" * 40)

    workflow = Workflow(
        id="test-onboarding",
        name="Test Onboarding",
        description="A minimal test workflow",
        team="default",
        nodes=[
            WorkflowNode(
                id="create_hr_record",
                name="Create Employee Record",
                description="Create HR record",
                service="hr",
                action="create_employee",
                actor="hr_manager",
                parameters=[
                    NodeParameter(name="employee_name", value="Alice Chen", description="Name"),
                    NodeParameter(name="role", value="Engineer", description="Role"),
                ],
                depends_on=[],
                outputs={"employee_id": "The created employee ID"},
            ),
            WorkflowNode(
                id="provision_google",
                name="Provision Google Workspace",
                description="Create Google account",
                service="google",
                action="provision_account",
                actor="it_admin",
                parameters=[
                    NodeParameter(
                        name="employee_name", value="Alice Chen", description="Name"
                    ),
                ],
                depends_on=["create_hr_record"],
                outputs={"email": "The provisioned email"},
            ),
            WorkflowNode(
                id="invite_slack",
                name="Invite to Slack",
                description="Add to Slack",
                service="slack",
                action="invite_user",
                actor="it_admin",
                parameters=[
                    NodeParameter(
                        name="email",
                        value="alice.chen@company.com",
                        description="Email",
                    ),
                    NodeParameter(
                        name="channel_name", value="#general", description="Channel"
                    ),
                ],
                depends_on=["provision_google"],
                outputs={},
            ),
        ],
        edges=[
            WorkflowEdge(source="create_hr_record", target="provision_google"),
            WorkflowEdge(source="provision_google", target="invite_slack"),
        ],
        parameters={"employee_name": "Alice Chen", "role": "Engineer"},
    )

    # Round-trip through JSON
    json_str = workflow.model_dump_json(indent=2)
    parsed = Workflow.model_validate_json(json_str)

    assert parsed.id == workflow.id
    assert len(parsed.nodes) == 3
    assert parsed.nodes[1].depends_on == ["create_hr_record"]
    print("[PASS] Workflow round-trips through JSON correctly")
    print(f"       {len(parsed.nodes)} nodes, {len(parsed.edges)} edges")
    print()
    return workflow


# ---------------------------------------------------------------------------
# Test 2: Simulator services
# ---------------------------------------------------------------------------


def test_simulator_correct_order():
    """Call services in the correct dependency order — should succeed."""
    print("Test 2a: Simulator — correct order")
    print("-" * 40)

    state = SimulatorState()
    trace = ExecutionTrace()
    from backend.simulator.services import GoogleService, HRService, SlackService

    hr = HRService(state, trace)
    google = GoogleService(state, trace)
    slack = SlackService(state, trace)

    # Correct order: HR -> Google -> Slack
    hr_result = hr.create_employee("n1", employee_name="Alice Chen", role="Engineer")
    print(f"  HR:     {hr_result}")

    google_result = google.provision_account("n2", employee_name="Alice Chen")
    print(f"  Google: {google_result}")

    slack_result = slack.invite_user(
        "n3", email=google_result["email"], channel_name="#general"
    )
    print(f"  Slack:  {slack_result}")

    assert len(trace.steps) == 3
    assert all(s.status == "success" for s in trace.steps)
    print("[PASS] All services succeeded in correct order")
    print()


def test_simulator_wrong_order():
    """Call services in the wrong order — should fail with precondition error."""
    print("Test 2b: Simulator — wrong order")
    print("-" * 40)

    state = SimulatorState()
    trace = ExecutionTrace()
    from backend.simulator.services import GoogleService

    google = GoogleService(state, trace)

    try:
        # Try to provision Google without HR record
        google.provision_account("n1", employee_name="Bob Smith")
        print("[FAIL] Expected ServiceError but got none")
    except ServiceError as e:
        print(f"  Got expected error: {e}")
        print("[PASS] Precondition check caught wrong order")
    print()


def test_simulator_failure_injection():
    """Test failure injection via FailureConfig."""
    print("Test 2c: Simulator — failure injection")
    print("-" * 40)

    config = FailureConfig(
        rules={
            "slack.create_channel": FailureRule(
                error_type="rate_limit",
                message="Rate limit exceeded — try again later",
                probability=1.0,
            )
        }
    )

    rule = config.should_fail("slack", "create_channel")
    assert rule is not None
    assert rule.error_type == "rate_limit"
    print(f"  Failure triggered: [{rule.error_type}] {rule.message}")

    no_rule = config.should_fail("hr", "create_employee")
    assert no_rule is None
    print("  No failure for hr.create_employee: correct")
    print("[PASS] Failure injection works")
    print()


# ---------------------------------------------------------------------------
# Test 3: DAG Executor
# ---------------------------------------------------------------------------


async def test_executor():
    """Build a small 3-node DAG, execute it, verify topological ordering and trace."""
    print("Test 3: DAG Executor")
    print("-" * 40)

    workflow = Workflow(
        id="executor-test",
        name="Executor Test",
        description="A 3-node test DAG",
        team="default",
        nodes=[
            WorkflowNode(
                id="create_hr_record",
                name="Create HR Record",
                description="Create employee record",
                service="hr",
                action="create_employee",
                actor="hr_manager",
                parameters=[
                    NodeParameter(name="employee_name", value="Alice Chen", description="Name"),
                    NodeParameter(name="role", value="Engineer", description="Role"),
                ],
                depends_on=[],
                outputs={"employee_id": "Created ID"},
            ),
            WorkflowNode(
                id="provision_google",
                name="Provision Google",
                description="Create Google account",
                service="google",
                action="provision_account",
                actor="it_admin",
                parameters=[
                    NodeParameter(
                        name="employee_name", value="Alice Chen", description="Name"
                    ),
                ],
                depends_on=["create_hr_record"],
                outputs={"email": "Email"},
            ),
            WorkflowNode(
                id="add_to_github",
                name="Add to GitHub",
                description="Add to GitHub org",
                service="github",
                action="add_to_org",
                actor="it_admin",
                parameters=[
                    NodeParameter(name="username", value="achen", description="GH username"),
                    NodeParameter(
                        name="employee_name", value="Alice Chen", description="Name"
                    ),
                ],
                depends_on=["create_hr_record"],
                outputs={},
            ),
        ],
        edges=[
            WorkflowEdge(source="create_hr_record", target="provision_google"),
            WorkflowEdge(source="create_hr_record", target="add_to_github"),
        ],
        parameters={"employee_name": "Alice Chen"},
    )

    state, trace, services, failure_config = create_simulator()
    executor = WorkflowExecutor(state=state, trace=trace, services=services)
    report = await executor.execute(workflow)

    print(
        f"  Total: {report.total_steps}, Success: {report.successful}, "
        f"Failed: {report.failed}, Skipped: {report.skipped}"
    )

    # Verify topological order
    executed_ids = [step.node_id for step in report.trace.steps]
    assert executed_ids.index("create_hr_record") < executed_ids.index("provision_google")
    assert executed_ids.index("create_hr_record") < executed_ids.index("add_to_github")
    assert report.successful == 3
    assert report.failed == 0
    print("[PASS] Executor ran DAG in correct topological order")

    print()
    print(report.to_markdown())
    print()


# ---------------------------------------------------------------------------
# Test 4: Executor with failure injection
# ---------------------------------------------------------------------------


async def test_executor_with_failures():
    """Test that failure injection causes downstream nodes to be skipped."""
    print("Test 4: Executor with failure injection")
    print("-" * 40)

    workflow = Workflow(
        id="failure-test",
        name="Failure Test",
        description="Test failure cascading",
        team="default",
        nodes=[
            WorkflowNode(
                id="create_hr_record",
                name="Create HR Record",
                description="Create employee record",
                service="hr",
                action="create_employee",
                actor="hr_manager",
                parameters=[
                    NodeParameter(name="employee_name", value="Alice Chen", description="Name"),
                ],
                depends_on=[],
                outputs={},
            ),
            WorkflowNode(
                id="provision_google",
                name="Provision Google",
                description="Create Google account",
                service="google",
                action="provision_account",
                actor="it_admin",
                parameters=[
                    NodeParameter(
                        name="employee_name", value="Alice Chen", description="Name"
                    ),
                ],
                depends_on=["create_hr_record"],
                outputs={},
            ),
            WorkflowNode(
                id="invite_slack",
                name="Invite to Slack",
                description="Invite to Slack",
                service="slack",
                action="invite_user",
                actor="it_admin",
                parameters=[
                    NodeParameter(name="email", value="alice@co.com", description="Email"),
                ],
                depends_on=["provision_google"],
                outputs={},
            ),
        ],
        edges=[
            WorkflowEdge(source="create_hr_record", target="provision_google"),
            WorkflowEdge(source="provision_google", target="invite_slack"),
        ],
        parameters={},
    )

    failure_config = FailureConfig(
        rules={
            "google.provision_account": FailureRule(
                error_type="permission_denied",
                message="Admin access required",
                probability=1.0,
            )
        }
    )

    state, trace, services, _ = create_simulator()
    executor = WorkflowExecutor(
        state=state, trace=trace, services=services, failure_config=failure_config
    )
    report = await executor.execute(workflow)

    print(
        f"  Total: {report.total_steps}, Success: {report.successful}, "
        f"Failed: {report.failed}, Skipped: {report.skipped}"
    )

    assert report.successful == 1  # Only HR succeeds
    assert report.failed == 1  # Google fails
    assert report.skipped == 1  # Slack skipped
    print("[PASS] Failure cascaded correctly — downstream node was skipped")
    print()


# ---------------------------------------------------------------------------
# Test 5: API catalog search
# ---------------------------------------------------------------------------


def test_api_catalog_search():
    """Verify search returns correct services for various queries."""
    print("Test 5: API Catalog Search")
    print("-" * 40)

    from backend.agents.api_catalog import search_api_catalog

    # Search for employee-related APIs
    results = search_api_catalog("create employee record")
    assert len(results) > 0
    assert results[0].service == "hr"
    assert results[0].action == "create_employee"
    print(f"  'create employee record' -> {results[0].service}.{results[0].action} [OK]")

    # Search for email-related APIs
    results = search_api_catalog("send email notification")
    services_found = {r.service for r in results}
    assert "google" in services_found
    print(f"  'send email notification' -> found google service [OK]")

    # Search for GitHub-related APIs
    results = search_api_catalog("grant repository access")
    assert any(r.action == "grant_repo_access" for r in results)
    print(f"  'grant repository access' -> found grant_repo_access [OK]")

    # Search for Slack-related APIs
    results = search_api_catalog("invite user to channel slack")
    assert any(r.service == "slack" and r.action == "invite_user" for r in results)
    print(f"  'invite user to channel slack' -> found slack.invite_user [OK]")

    # Search for calendar-related APIs
    results = search_api_catalog("schedule meeting calendar")
    assert any(r.action == "create_calendar_event" for r in results)
    print(f"  'schedule meeting calendar' -> found create_calendar_event [OK]")

    print("[PASS] API catalog search works correctly")
    print()


# ---------------------------------------------------------------------------
# Test 6: KB search
# ---------------------------------------------------------------------------


def test_kb_search():
    """Verify search returns correct KB sections."""
    print("Test 6: KB Search")
    print("-" * 40)

    from backend.agents.kb_search import load_kb_sections, search_knowledge_base

    # Load sections
    sections = load_kb_sections(team="default")
    assert len(sections) > 0
    print(f"  Loaded {len(sections)} KB sections")

    # List all section headings
    for s in sections:
        print(f"    [{s.file}] {s.heading}")

    # Search for onboarding policy
    results = search_knowledge_base("onboarding day 1 system access", team="default")
    assert len(results) > 0
    print(f"\n  'onboarding day 1 system access' -> {len(results)} results")
    print(f"    Top result: [{results[0].file}] {results[0].heading}")

    # Search for roles
    results = search_knowledge_base("IT Admin responsibilities access", team="default")
    assert len(results) > 0
    assert any("admin" in r.heading.lower() or "admin" in r.content.lower() for r in results)
    print(f"  'IT Admin responsibilities' -> found admin-related section [OK]")

    # Search for systems
    results = search_knowledge_base("Slack messaging channels", team="default")
    assert len(results) > 0
    print(f"  'Slack messaging channels' -> {len(results)} results [OK]")

    print("[PASS] KB search works correctly")
    print()


# ---------------------------------------------------------------------------
# Test 7: MCP server creation
# ---------------------------------------------------------------------------


def test_mcp_server_creation():
    """Verify factory returns valid MCP server config."""
    print("Test 7: MCP Server Creation")
    print("-" * 40)

    from backend.agents.tools import create_flowforge_mcp_server

    server = create_flowforge_mcp_server(team="default")

    # Should be a dict-like config with expected keys
    assert server is not None
    assert "type" in server
    assert server["type"] == "sdk"
    assert "name" in server
    assert server["name"] == "flowforge"
    print(f"  Server type: {server['type']}")
    print(f"  Server name: {server['name']}")
    print(f"  Has instance: {'instance' in server}")

    # Create with different team
    server2 = create_flowforge_mcp_server(team="engineering")
    assert server2 is not None
    assert server2["name"] == "flowforge"
    print(f"  Team override works: [OK]")

    print("[PASS] MCP server creation works correctly")
    print()


# ---------------------------------------------------------------------------
# Test 8: Workflow save
# ---------------------------------------------------------------------------


def test_workflow_save():
    """Verify save+load roundtrip via WorkflowStore."""
    print("Test 8: Workflow Save")
    print("-" * 40)

    tmp_dir = Path(tempfile.mkdtemp(prefix="flowforge-test-"))
    store = WorkflowStore(tmp_dir)

    workflow = Workflow(
        id="save-test",
        name="Save Test Workflow",
        description="Testing save and load",
        team="default",
        nodes=[
            WorkflowNode(
                id="step1",
                name="Step 1",
                description="First step",
                service="hr",
                action="create_employee",
                actor="hr_manager",
                parameters=[
                    NodeParameter(name="employee_name", value="Test User", description="Name"),
                ],
                depends_on=[],
                outputs={"employee_id": "ID"},
            ),
        ],
        edges=[],
        parameters={"employee_name": "Test User"},
    )

    # Save
    saved_id = store.save(workflow)
    assert saved_id == "save-test"
    print(f"  Saved workflow: {saved_id}")

    # Load
    loaded = store.load("save-test", team="default")
    assert loaded is not None
    assert loaded.id == workflow.id
    assert loaded.name == workflow.name
    assert len(loaded.nodes) == 1
    print(f"  Loaded workflow: {loaded.id} ({loaded.name})")

    # List
    all_workflows = store.list_by_team("default")
    assert len(all_workflows) == 1
    print(f"  Listed {len(all_workflows)} workflow(s)")

    # Delete
    deleted = store.delete("save-test", team="default")
    assert deleted
    assert store.load("save-test", team="default") is None
    print(f"  Deleted workflow: {saved_id}")

    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print("[PASS] Workflow save/load/list/delete works correctly")
    print()


# ---------------------------------------------------------------------------
# Test 9: Agent generation (end-to-end)
# ---------------------------------------------------------------------------


async def test_agent_generation():
    """Full end-to-end: agent produces workflow.json, executor runs it, report shows results."""
    print("Test 9: Agent Generation (end-to-end)")
    print("-" * 40)

    from backend.agents import generate_workflow

    tmp_dir = Path(tempfile.mkdtemp(prefix="flowforge-e2e-"))
    store = WorkflowStore(tmp_dir)

    description = "Create a Day 1 onboarding workflow for a new engineer"
    context = {
        "employee_name": "Alice Chen",
        "role": "Software Engineer",
    }

    print(f"  Request: {description}")
    print(f"  Context: {context}\n")

    workflow_data = None
    report_data = None
    workflow_saved = False
    has_error = False

    try:
        async for message in generate_workflow(
            description, context, workflow_store=store
        ):
            msg_type = message["type"]
            content = message["content"]

            if msg_type == "text":
                text = content[:200] + "..." if len(content) > 200 else content
                print(f"  [agent] {text}")
            elif msg_type == "tool_use":
                tool = content["tool"]
                inp = content.get("input", {})
                detail = inp.get("file_path") or inp.get("command", "")
                if detail:
                    print(f"  [tool]  {tool}: {str(detail)[:100]}")
                else:
                    print(f"  [tool]  {tool}")
            elif msg_type == "workflow":
                workflow_data = content
                print(
                    f"  [workflow] Parsed: {content['name']} ({len(content['nodes'])} nodes)"
                )
            elif msg_type == "execution_report":
                report_data = content
                r = content["report"]
                print(f"  [report] {r['successful']}/{r['total_steps']} steps passed")
            elif msg_type == "workflow_saved":
                workflow_saved = True
                print(f"  [saved] Workflow {content['workflow_id']} v{content['version']}")
            elif msg_type == "result":
                cost = content.get("cost_usd", 0)
                print(f"  [done]  Cost: ${cost:.4f}")
            elif msg_type == "error":
                print(f"  [error] {content}")
                has_error = True
            elif msg_type == "workspace":
                print(f"  [workspace] {content['path']}")
    except Exception as e:
        print(f"  [error] Exception: {e}")
        has_error = True

    print()
    if workflow_data:
        print(f"[PASS] Agent generated workflow: {workflow_data['name']}")
    else:
        print("[FAIL] No workflow data produced")

    if workflow_saved:
        print("[PASS] Workflow was saved to store")
    else:
        print("[INFO] Workflow was not saved (may have had failures)")

    if report_data:
        md = report_data.get("markdown", "")
        print()
        print(md[:500])
    else:
        print("[INFO] No execution report (agent may not have produced valid JSON)")

    # Cleanup
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print()
    return not has_error


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    print("=" * 60)
    print("FlowForge — Workflow Engine Tests")
    print("=" * 60)
    print()

    # Synchronous tests
    test_schema_validation()
    test_simulator_correct_order()
    test_simulator_wrong_order()
    test_simulator_failure_injection()

    # Async tests
    await test_executor()
    await test_executor_with_failures()

    # New deterministic tests (no API key needed)
    test_api_catalog_search()
    test_kb_search()
    test_mcp_server_creation()
    test_workflow_save()

    # End-to-end agent test (requires API key)
    print("=" * 60)
    print("Running agent end-to-end test (requires API key)...")
    print("=" * 60)
    print()
    await test_agent_generation()

    print("=" * 60)
    print("All tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
