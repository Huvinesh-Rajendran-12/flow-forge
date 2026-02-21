"""Mind orchestrator: currently runs a single focused Mind execution."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from tempfile import TemporaryDirectory

from .memory import MemoryManager
from .reasoning import run_mind_reasoning
from .schema import MemoryEntry, MindProfile
from .tools import create_mind_tools, tool_names


async def execute_task(
    *,
    mind: MindProfile,
    task: str,
    team: str,
    memories: list[MemoryEntry],
    memory_manager: MemoryManager,
) -> AsyncGenerator[dict, None]:
    """Execute one task with one Mind run.

    Note: automatic orchestration is intentionally minimal.
    Sub-agents are available only through the explicit spawn_agent tool.
    """
    with TemporaryDirectory(prefix="mind-") as workspace:

        async def _spawn_agent(objective: str, max_turns: int) -> str:
            chunks: list[str] = []

            with TemporaryDirectory(prefix="drone-") as drone_workspace:
                # Build a fresh per-drone toolset bound to the drone workspace.
                # Keep delegation explicit and one level deep by excluding spawn_agent.
                drone_tools = create_mind_tools(
                    team=team,
                    workspace_dir=drone_workspace,
                    memory_manager=memory_manager,
                    mind_id=mind.id,
                    spawn_agent_fn=_spawn_agent,
                    include_spawn_agent=False,
                )

                async for event in run_mind_reasoning(
                    mind=mind,
                    task=f"[Drone Objective] {objective}",
                    workspace_dir=drone_workspace,
                    team=team,
                    memories=memories,
                    tools=drone_tools,
                    allowed_tools=tool_names(drone_tools),
                    max_turns=max_turns,
                ):
                    if event.get("type") == "text" and isinstance(event.get("content"), str):
                        chunks.append(event["content"])

            if chunks:
                return "\n".join(chunks[-3:])
            return "Sub-agent completed with no textual output."

        tools = create_mind_tools(
            team=team,
            workspace_dir=workspace,
            memory_manager=memory_manager,
            mind_id=mind.id,
            spawn_agent_fn=_spawn_agent,
            include_spawn_agent=True,
        )

        yield {
            "type": "tool_registry",
            "content": {
                "tools": tool_names(tools),
            },
        }

        async for event in run_mind_reasoning(
            mind=mind,
            task=task,
            workspace_dir=workspace,
            team=team,
            memories=memories,
            tools=tools,
        ):
            yield event
