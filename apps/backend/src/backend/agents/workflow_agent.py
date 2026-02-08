"""Workflow agent that designs structured DAG workflows using Claude Agent SDK."""

import json
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator

from ..simulator import create_simulator
from ..workflow.executor import WorkflowExecutor
from ..workflow.schema import Workflow
from ..workflow.store import WorkflowStore
from .base import run_agent
from .tools import create_flowforge_mcp_server

MAX_FIX_ATTEMPTS = 2

FIX_SYSTEM_PROMPT = """\
You are FlowForge, an AI agent that fixes workflow JSON files.

You will be given an execution report showing which workflow nodes failed and why.
Read the existing workflow.json, diagnose the issue, fix it, and write the corrected file back.

{schema_description}

## Available Tools
- **search_apis**: Search available service APIs to find correct actions and parameters
- **search_knowledge_base**: Search the organization's knowledge base for policies and procedures

## Rules
- Only modify what is necessary to fix the reported failures
- Use search_apis to verify correct service actions and parameter names
- Ensure all node dependencies remain valid
- The edges array must mirror the depends_on relationships
"""

WORKFLOW_SCHEMA_DESCRIPTION = """\
The workflow JSON must conform to this schema:

```json
{
  "id": "string — unique workflow identifier (kebab-case)",
  "name": "string — human-readable name",
  "description": "string — what this workflow accomplishes",
  "team": "string — team whose KB was used (e.g., 'default', 'engineering')",
  "nodes": [
    {
      "id": "string — unique node ID (snake_case)",
      "name": "string — display name",
      "description": "string — what this step does",
      "service": "string — one of: slack, jira, google, hr, github",
      "action": "string — service method to call, e.g., create_channel, send_message, provision_account, create_employee, add_to_org, grant_repo_access, create_issue, create_epic, assign_issue, invite_user, send_email, create_calendar_event, enroll_benefits",
      "actor": "string — responsible role: hr_manager, it_admin, team_lead, new_employee",
      "parameters": [
        {
          "name": "string — parameter name matching the service method kwarg",
          "value": "any — the value; use {{param_name}} for global params, {{node_id.output_key}} for upstream outputs",
          "description": "string — human-readable description",
          "required": true
        }
      ],
      "depends_on": ["list of node IDs this step depends on"],
      "outputs": {"output_name": "description of what this output contains"}
    }
  ],
  "edges": [
    {"source": "node_id", "target": "node_id"}
  ],
  "parameters": {
    "employee_name": "Alice Chen",
    "role": "Software Engineer"
  },
  "version": 1
}
```
"""

EXAMPLE_WORKFLOW_JSON = """\
{
  "id": "day1-onboarding",
  "name": "Day 1 Onboarding",
  "description": "Provisions all accounts and sends welcome materials for a new hire's first day",
  "team": "default",
  "nodes": [
    {
      "id": "create_hr_record",
      "name": "Create Employee Record",
      "description": "Create the employee's HR record in the HR Portal",
      "service": "hr",
      "action": "create_employee",
      "actor": "hr_manager",
      "parameters": [
        {"name": "employee_name", "value": "{{employee_name}}", "description": "Full name of the new employee", "required": true},
        {"name": "role", "value": "{{role}}", "description": "Job title", "required": true},
        {"name": "department", "value": "{{department}}", "description": "Department", "required": false}
      ],
      "depends_on": [],
      "outputs": {"employee_id": "The created employee ID"}
    },
    {
      "id": "provision_google",
      "name": "Provision Google Workspace",
      "description": "Create Google Workspace account for email, calendar, and drive",
      "service": "google",
      "action": "provision_account",
      "actor": "it_admin",
      "parameters": [
        {"name": "employee_name", "value": "{{employee_name}}", "description": "Full name", "required": true},
        {"name": "email", "value": "{{employee_name}}.lowercase@company.com", "description": "Work email", "required": true}
      ],
      "depends_on": ["create_hr_record"],
      "outputs": {"email": "The provisioned email address"}
    },
    {
      "id": "invite_slack",
      "name": "Invite to Slack",
      "description": "Create Slack account and invite to required channels",
      "service": "slack",
      "action": "invite_user",
      "actor": "it_admin",
      "parameters": [
        {"name": "email", "value": "{{provision_google.email}}", "description": "User's email for Slack invite", "required": true},
        {"name": "channel_name", "value": "#general", "description": "Channel to invite to", "required": true}
      ],
      "depends_on": ["provision_google"],
      "outputs": {}
    }
  ],
  "edges": [
    {"source": "create_hr_record", "target": "provision_google"},
    {"source": "provision_google", "target": "invite_slack"}
  ],
  "parameters": {
    "employee_name": "Alice Chen",
    "role": "Software Engineer",
    "department": "Engineering"
  },
  "version": 1
}
"""

GENERATE_SYSTEM_PROMPT = """\
You are FlowForge, an AI agent that designs workflow automations as structured JSON DAGs.

## Your Task
1. Use the `search_knowledge_base` tool to find relevant policies, roles, and procedures for the request
2. Use the `search_apis` tool to discover which APIs and actions are available
3. Design a workflow as a structured JSON DAG based on what you learned
4. Write the workflow JSON to `workflow.json` using the Write tool
5. Review: verify all required policy steps are included, dependencies are correct, roles match

## Available Tools
- **search_apis**: Search available service APIs by intent (e.g., "create employee", "send email", "grant repo access")
- **search_knowledge_base**: Search the organization's knowledge base for policies, roles, systems, and procedures

## What's Searchable
- **APIs**: HR, Google Workspace, Slack, Jira, GitHub — employee management, email, calendar, messaging, project tracking, code access
- **Knowledge Base**: Onboarding policies, system documentation, role definitions, compliance requirements

## Workflow JSON Format
{schema_description}

## Example
{example_workflow_json}

## Rules
- Every node MUST specify a service, action, actor, and parameters
- Dependencies must reflect the policy (e.g., Google Workspace depends on HR record)
- Use search_knowledge_base to find which steps are REQUIRED by policy
- Use search_apis to find the correct service, action, and parameters for each step
- Include all REQUIRED steps from the policy
- Use {{{{param_name}}}} syntax for global parameters (e.g., {{{{employee_name}}}})
- Use {{{{node_id.output_key}}}} syntax to reference outputs from upstream nodes
- The edges array should mirror the depends_on relationships
- DO NOT use task/todo management tools
"""

MODIFY_SYSTEM_PROMPT = """\
You are FlowForge. A team wants to customize an existing workflow.

## Current Workflow
```json
{existing_workflow_json}
```

## Workflow JSON Format
{schema_description}

## Available Tools
- **search_apis**: Search available service APIs by intent (e.g., "create employee", "send email")
- **search_knowledge_base**: Search the organization's knowledge base for policies, roles, systems

## Instructions
Modify the workflow based on the user's request. You may:
- Add new nodes (with correct dependencies)
- Remove nodes (and rewire dependencies of nodes that depended on them)
- Change node parameters
- Swap a service (e.g., Jira -> Linear)
- Change the actor for a step

Use `search_apis` to discover available actions if adding new steps.
Use `search_knowledge_base` to verify policy compliance.

Write the updated workflow JSON to `workflow.json` using the Write tool.
Increment the version number by 1.

## Rules
- Maintain valid dependency chains — if you remove a node, update depends_on of downstream nodes
- The edges array must mirror the depends_on relationships
- DO NOT use task/todo management tools
"""


async def generate_workflow(
    description: str,
    context: dict[str, Any] | None = None,
    team: str = "default",
    existing_workflow: Workflow | None = None,
    workflow_store: WorkflowStore | None = None,
    session_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Generate or modify a structured DAG workflow from natural language.

    Args:
        description: Natural language description of the desired workflow
        context: Optional additional context (employee name, department, etc.)
        team: Team whose KB to load (defaults to "default")
        existing_workflow: If provided, agent modifies this workflow instead of creating new
        workflow_store: If provided, save the workflow after successful generation
        session_id: If provided, resume an existing agent session for multi-turn refinement

    Yields:
        Message dicts with type and content
    """
    workspace = tempfile.mkdtemp(prefix="flowforge-")
    workflow_file = Path(workspace) / "workflow.json"

    mcp_server = create_flowforge_mcp_server(team=team)

    if session_id:
        # Follow up turn: the resumed session already has the system prompt
        prompt = (
            f"New workspace directory: {workspace}\n"
            f"Write all files there using absolute paths (e.g., {workspace}/workflow.json).\n\n"
        )
        if existing_workflow:
            prompt += (
                f"Current workflow JSON:\n```json\n"
                f"{existing_workflow.model_dump_json(indent=2)}\n```\n\n"
            )
        prompt += f"User request: {description}"
        if context:
            prompt += "\n\nAdditional context:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"

        system_prompt = ""
    else:
        if existing_workflow:
            system_prompt = MODIFY_SYSTEM_PROMPT.format(
                existing_workflow_json=existing_workflow.model_dump_json(indent=2),
                schema_description=WORKFLOW_SCHEMA_DESCRIPTION,
            )
        else:
            system_prompt = GENERATE_SYSTEM_PROMPT.format(
                schema_description=WORKFLOW_SCHEMA_DESCRIPTION,
                example_workflow_json=EXAMPLE_WORKFLOW_JSON,
            )

        prompt = (
            f"Your workspace directory is: {workspace}\n"
            f"Write all files there using absolute paths (e.g., {workspace}/workflow.json).\n\n"
        )

        if existing_workflow:
            prompt += f"Modify the existing workflow based on the following request:\n\n{description}"
        else:
            prompt += f"Design a workflow DAG for the following request:\n\n{description}"

        if context:
            prompt += "\n\nAdditional context:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"

    async for message in run_agent(
        prompt=prompt,
        system_prompt=system_prompt,
        workspace_dir=workspace,
        allowed_tools=[
            "Read", "Write", "Edit", "Bash", "Glob",
            "mcp__flowforge__search_apis",
            "mcp__flowforge__search_knowledge_base",
        ],
        max_turns=30,
        mcp_servers={"flowforge": mcp_server},
        session_id=session_id,
    ):
        yield message

    if not workflow_file.exists():
        yield {"type": "error", "content": "Agent did not produce workflow.json"}
        yield {"type": "workspace", "content": {"path": workspace}}
        return

    fix_system_prompt = FIX_SYSTEM_PROMPT.format(
        schema_description=WORKFLOW_SCHEMA_DESCRIPTION,
    )

    report = None
    for attempt in range(1, MAX_FIX_ATTEMPTS + 2):
        try:
            workflow_data = json.loads(workflow_file.read_text())
            workflow = Workflow.model_validate(workflow_data)
        except Exception as e:
            yield {
                "type": "error",
                "content": f"Failed to parse workflow.json (attempt {attempt}): {e}",
            }
            if attempt > MAX_FIX_ATTEMPTS:
                break

            yield {
                "type": "text",
                "content": f"Parse error in workflow.json. "
                f"Running self-correction (attempt {attempt}/{MAX_FIX_ATTEMPTS})...",
            }

            async for message in run_agent(
                prompt=(
                    f"The workflow.json file at {workflow_file} failed to parse "
                    f"with the following error:\n\n{e}\n\n"
                    f"Read the file, fix the JSON, and write it back."
                ),
                system_prompt=fix_system_prompt,
                workspace_dir=workspace,
                allowed_tools=[
                    "Read", "Write", "Edit",
                    "mcp__flowforge__search_apis",
                    "mcp__flowforge__search_knowledge_base",
                ],
                max_turns=10,
                mcp_servers={"flowforge": mcp_server},
            ):
                yield message
            continue

        yield {"type": "workflow", "content": workflow.model_dump()}

        state, trace, services, failure_config = create_simulator()
        executor = WorkflowExecutor(
            state=state,
            trace=trace,
            services=services,
            failure_config=failure_config,
        )
        report = await executor.execute(workflow)

        yield {
            "type": "execution_report",
            "content": {
                "report": report.to_dict(),
                "markdown": report.to_markdown(),
                "attempt": attempt,
            },
        }

        if report.failed == 0:
            break

        if attempt > MAX_FIX_ATTEMPTS:
            break

        yield {
            "type": "text",
            "content": f"Execution had {report.failed} failure(s). "
            f"Running self-correction (attempt {attempt}/{MAX_FIX_ATTEMPTS})...",
        }

        async for message in run_agent(
            prompt=(
                f"The workflow at {workflow_file} was executed but had failures.\n\n"
                f"## Execution Report\n\n{report.to_markdown()}\n\n"
                f"Read the workflow.json, fix the issues described above, "
                f"and write the corrected file back."
            ),
            system_prompt=fix_system_prompt,
            workspace_dir=workspace,
            allowed_tools=[
                "Read", "Write", "Edit",
                "mcp__flowforge__search_apis",
                "mcp__flowforge__search_knowledge_base",
            ],
            max_turns=10,
            mcp_servers={"flowforge": mcp_server},
        ):
            yield message

    if workflow_store and report and report.failed == 0:
        workflow_store.save(workflow)
        yield {
            "type": "workflow_saved",
            "content": {
                "workflow_id": workflow.id,
                "team": workflow.team,
                "version": workflow.version,
            },
        }

    yield {"type": "workspace", "content": {"path": workspace}}
