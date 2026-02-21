"""Connector builder agent — generates a Python connector for an unknown service.

Flow:
    1. Creates a temp workspace
    2. Runs a focused agent (via run_agent) with write_file + run_command tools
    3. Agent writes connector.py to the workspace
    4. validate_connector_file() checks the file structurally
    5. If valid: copies to custom_connectors/{service_name}.py
    6. Yields SSE-compatible dicts throughout (forwarded to the client)
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator

from ...agents.base import run_agent
from ...agents.tools import DEFAULT_TOOL_NAMES
from ..registry import CUSTOM_CONNECTOR_DIR, is_safe_service_name
from .template import BUILDER_SYSTEM_PROMPT, BUILDER_USER_PROMPT
from .validator import validate_connector_file


async def build_connector(
    service_name: str,
    required_actions: list[str],
    workflow_context: str,
    team: str = "default",
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the connector builder agent and persist the validated result.

    Yields SSE dicts so the pipeline can stream build progress to the client.
    Types used: "text", "tool_use", "tool_result", "connector_built", "error"
    """
    if not is_safe_service_name(service_name):
        yield {
            "type": "error",
            "content": (
                f"Refusing to build connector for invalid service name '{service_name}'. "
                "Use only letters, numbers, and underscores."
            ),
        }
        return

    workspace = tempfile.mkdtemp(prefix="connector-build-")
    connector_file = Path(workspace) / "connector.py"
    service_name_cap = service_name.capitalize()

    try:
        yield {
            "type": "text",
            "content": (
                f"No connector found for service '{service_name}'. "
                f"Building one automatically..."
            ),
        }

        action_list = "\n".join(f"  - {a}" for a in required_actions)

        system_prompt = BUILDER_SYSTEM_PROMPT.format(
            ServiceName=service_name_cap,
            service_name=service_name,
            workspace=workspace,
        )

        user_prompt = BUILDER_USER_PROMPT.format(
            service_name=service_name,
            ServiceName=service_name_cap,
            action_list=action_list,
            workflow_context=workflow_context,
            workspace=workspace,
        )

        async for message in run_agent(
            prompt=user_prompt,
            system_prompt=system_prompt,
            workspace_dir=workspace,
            team=team,
            allowed_tools=DEFAULT_TOOL_NAMES,
            max_turns=15,
        ):
            yield message

        # Validate the produced file
        if not connector_file.exists():
            yield {
                "type": "error",
                "content": (
                    f"Builder agent did not produce connector.py for '{service_name}'. "
                    f"The service will fall back to the simulator."
                ),
            }
            return

        errors = validate_connector_file(connector_file, service_name, required_actions)
        if errors:
            yield {
                "type": "error",
                "content": (
                    f"Connector validation failed for '{service_name}': "
                    + "; ".join(errors)
                    + ". The service will fall back to the simulator."
                ),
            }
            return

        # Persist to custom_connectors/
        CUSTOM_CONNECTOR_DIR.mkdir(parents=True, exist_ok=True)
        dest = CUSTOM_CONNECTOR_DIR / f"{service_name}.py"
        shutil.copy2(str(connector_file), str(dest))

        yield {
            "type": "connector_built",
            "content": {
                "service": service_name,
                "path": str(dest),
                "actions": required_actions,
            },
        }
        yield {
            "type": "text",
            "content": (
                f"Connector for '{service_name}' built and saved successfully. "
                f"Resuming workflow execution..."
            ),
        }

    except Exception as exc:
        yield {
            "type": "error",
            "content": f"Connector builder failed for '{service_name}': {exc}",
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
