"""Mind tool primitives for Phase 2 foundation."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pi_agent_core import AgentTool, AgentToolResult, AgentToolSchema, TextContent

from ..memory import MemoryManager
from ..schema import MemoryEntry

DEFAULT_SPAWN_MAX_CALLS = 3
DEFAULT_SPAWN_MAX_TURNS = 20


def _text_result(value: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=value)])


def create_memory_tools(memory_manager: MemoryManager, mind_id: str) -> list[AgentTool]:
    async def memory_save_execute(tool_call_id: str, params: dict[str, Any], **_: object) -> AgentToolResult:
        entry = MemoryEntry(
            mind_id=mind_id,
            content=params["content"],
            category=params.get("category"),
            relevance_keywords=params.get("relevance_keywords", []),
        )
        memory_manager.save(entry)
        return _text_result(f"Saved memory: {entry.id}")

    async def memory_search_execute(tool_call_id: str, params: dict[str, Any], **_: object) -> AgentToolResult:
        query = params["query"]
        top_k = int(params.get("top_k", 5))
        results = memory_manager.search(mind_id, query, top_k=top_k)
        payload = [item.model_dump(mode="json") for item in results]
        return _text_result(json.dumps(payload, indent=2))

    return [
        AgentTool(
            name="memory_save",
            description="Save a persistent memory for this Mind.",
            parameters=AgentToolSchema(
                properties={
                    "content": {"type": "string", "description": "Memory content to save."},
                    "category": {"type": "string", "description": "Optional category tag."},
                    "relevance_keywords": {
                        "type": "array",
                        "description": "Optional keywords used to improve retrieval.",
                        "items": {"type": "string"},
                    },
                },
                required=["content"],
            ),
            execute=memory_save_execute,
        ),
        AgentTool(
            name="memory_search",
            description="Search persistent memories for this Mind by query.",
            parameters=AgentToolSchema(
                properties={
                    "query": {"type": "string", "description": "Search query text."},
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results.",
                        "default": 5,
                    },
                },
                required=["query"],
            ),
            execute=memory_search_execute,
        ),
    ]


def create_spawn_agent_tool(
    spawn_agent_fn: Callable[[str, int], Awaitable[str]],
    *,
    max_calls: int = DEFAULT_SPAWN_MAX_CALLS,
    max_turns_cap: int = DEFAULT_SPAWN_MAX_TURNS,
) -> AgentTool:
    spawn_calls = 0

    async def spawn_agent_execute(tool_call_id: str, params: dict[str, Any], **_: object) -> AgentToolResult:
        nonlocal spawn_calls

        spawn_calls += 1
        if spawn_calls > max_calls:
            return _text_result(f"spawn_agent call limit reached ({max_calls}). Continue without spawning.")

        objective = params["objective"]
        max_turns = int(params.get("max_turns", 12))
        max_turns = max(1, min(max_turns, max_turns_cap))
        result = await spawn_agent_fn(objective, max_turns)
        return _text_result(result)

    return AgentTool(
        name="spawn_agent",
        description="Spawn a focused Drone-style sub-agent for a specific objective.",
        parameters=AgentToolSchema(
            properties={
                "objective": {"type": "string", "description": "Focused sub-task objective."},
                "max_turns": {
                    "type": "integer",
                    "description": "Maximum turns for the sub-agent run.",
                    "default": 12,
                },
            },
            required=["objective"],
        ),
        execute=spawn_agent_execute,
    )
