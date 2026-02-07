"""Base agent using Claude Agent SDK for FlowForge."""

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from ..config import get_settings

KB_DIR = Path(__file__).resolve().parents[3] / "kb"


def load_knowledge_base(team: str = "default") -> str:
    """Load all markdown files from the knowledge base directory.

    Loads from the team-specific folder, falling back to default/ for
    any files the team folder doesn't override.
    """
    default_dir = KB_DIR / "default"
    team_dir = KB_DIR / team

    if not default_dir.exists():
        return ""

    # Collect files: start with defaults, override with team-specific
    files: dict[str, Path] = {}
    for md_file in sorted(default_dir.glob("*.md")):
        files[md_file.name] = md_file

    if team != "default" and team_dir.exists():
        for md_file in sorted(team_dir.glob("*.md")):
            files[md_file.name] = md_file

    sections = []
    for name in sorted(files):
        content = files[name].read_text()
        sections.append(f"## {name.removesuffix('.md').replace('_', ' ').title()}\n\n{content}")
    return "\n\n---\n\n".join(sections)


async def run_agent(
    prompt: str,
    system_prompt: str,
    workspace_dir: str,
    allowed_tools: Optional[list[str]] = None,
    max_turns: int = 50,
    mcp_servers: Optional[dict] = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run a Claude Agent SDK agent and yield messages as they arrive.

    Yields dicts with:
      - type: "text" | "tool_use" | "result" | "error"
      - content: the relevant payload
    """
    settings = get_settings()

    if allowed_tools is None:
        allowed_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

    options = ClaudeAgentOptions(
        model=settings.default_model,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        permission_mode="bypassPermissions",
        cwd=workspace_dir,
        mcp_servers=mcp_servers or {},
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield {"type": "text", "content": block.text}
                    elif isinstance(block, ToolUseBlock):
                        yield {
                            "type": "tool_use",
                            "content": {
                                "tool": block.name,
                                "input": getattr(block, "input", {}),
                            },
                        }
            elif isinstance(message, ResultMessage):
                yield {
                    "type": "result",
                    "content": {
                        "subtype": message.subtype,
                        "cost_usd": message.total_cost_usd,
                        "usage": message.usage,
                    },
                }
    except Exception as e:
        yield {"type": "error", "content": str(e)}
