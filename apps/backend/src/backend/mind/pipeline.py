"""Main execution pipeline for Mind task delegation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from .memory import MemoryManager
from .orchestrator import execute_task
from .schema import MemoryEntry, Task
from .store import MindStore

MAX_STREAM_EVENTS = 250
MAX_AUTOSAVE_MEMORIES_PER_RUN = 1


async def delegate_to_mind(
    *,
    mind_store: MindStore,
    memory_manager: MemoryManager,
    mind_id: str,
    description: str,
    team: str = "default",
) -> AsyncGenerator[dict, None]:
    """Delegate a task to a Mind and stream execution events."""
    mind = mind_store.load_mind(mind_id)
    if mind is None:
        yield {"type": "error", "content": f"Mind '{mind_id}' not found"}
        return

    task = Task(mind_id=mind_id, description=description, status="running")
    mind_store.save_task(mind_id, task)

    trace_events: list[dict] = []

    def _record(event: dict) -> None:
        trace_events.append(
            {
                "type": event.get("type"),
                "content": event.get("content"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    event_count = 0
    latest_text: str | None = None
    autosaved_memories = 0
    run_failure_reason: str | None = None

    start_event = {
        "type": "task_started",
        "content": {"task_id": task.id, "mind_id": mind_id},
    }
    _record(start_event)
    yield start_event

    memories = memory_manager.search(mind_id, description, top_k=8)
    memory_event = {
        "type": "memory_context",
        "content": {"count": len(memories), "memory_ids": [m.id for m in memories]},
    }
    _record(memory_event)
    yield memory_event

    try:
        async for event in execute_task(
            mind=mind,
            task=description,
            team=team,
            memories=memories,
            memory_manager=memory_manager,
        ):
            event_count += 1
            if event_count > MAX_STREAM_EVENTS:
                raise RuntimeError(f"Event limit reached ({MAX_STREAM_EVENTS})")

            event_type = event.get("type")
            content = event.get("content")

            if event_type == "text" and isinstance(content, str):
                latest_text = content

            if event_type == "result" and isinstance(content, dict):
                final_text = content.get("final_text")
                if isinstance(final_text, str) and final_text.strip():
                    latest_text = final_text.strip()

                subtype = content.get("subtype")
                error_message = content.get("error_message")
                if isinstance(subtype, str) and subtype in {"error", "aborted"}:
                    if isinstance(error_message, str) and error_message.strip():
                        run_failure_reason = error_message.strip()
                    else:
                        run_failure_reason = f"Mind run ended with subtype={subtype}"

            _record(event)
            yield event

        if run_failure_reason:
            raise RuntimeError(run_failure_reason)

        task.status = "completed"
        task.result = latest_text
        task.completed_at = datetime.now(timezone.utc)
        mind_store.save_task(mind_id, task)

        if latest_text and autosaved_memories < MAX_AUTOSAVE_MEMORIES_PER_RUN:
            memory = MemoryEntry(
                mind_id=mind_id,
                content=f"Completed task: {description}\nResult: {latest_text}",
                category="task_result",
                relevance_keywords=["task", "result", "completion"],
            )
            memory_manager.save(memory)
            autosaved_memories += 1

            memory_saved_event = {
                "type": "memory_saved",
                "content": {
                    "id": memory.id,
                    "mind_id": mind_id,
                    "category": memory.category,
                },
            }
            _record(memory_saved_event)
            yield memory_saved_event

    except Exception as exc:
        task.status = "failed"
        task.result = str(exc)
        task.completed_at = datetime.now(timezone.utc)
        mind_store.save_task(mind_id, task)
        error_event = {"type": "error", "content": f"Mind execution failed: {exc}"}
        _record(error_event)
        yield error_event
    finally:
        complete_event = {
            "type": "task_finished",
            "content": {"task_id": task.id, "status": task.status},
        }
        _record(complete_event)
        mind_store.save_task_trace(mind_id, task.id, trace_events)
        yield complete_event
