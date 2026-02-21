"""Factory for assembling the current Mind toolset."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pi_agent_core import AgentTool

from ...agents.tools import create_flowforge_tools
from ..memory import MemoryManager
from .primitives import create_memory_tools, create_spawn_agent_tool


def create_mind_tools(
    *,
    team: str,
    workspace_dir: str,
    memory_manager: MemoryManager,
    mind_id: str,
    spawn_agent_fn: Callable[[str, int], Awaitable[str]],
    include_spawn_agent: bool = True,
) -> list[AgentTool]:
    tools = [
        *create_flowforge_tools(team=team, workspace_dir=workspace_dir),
        *create_memory_tools(memory_manager=memory_manager, mind_id=mind_id),
    ]

    if include_spawn_agent:
        tools.append(create_spawn_agent_tool(spawn_agent_fn))

    return tools


def tool_names(tools: list[AgentTool]) -> list[str]:
    return sorted([tool.name for tool in tools])
