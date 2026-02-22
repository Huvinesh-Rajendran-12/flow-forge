# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
cd apps/backend

uv sync                                                    # Install/update dependencies
uv run uvicorn backend.main:app --reload --port 8000       # Start dev server
uv run pytest tests/test_mind_api.py tests/test_mind_persistence.py  # Run Mind unit tests
uv run pytest tests/test_integration_mind_openrouter.py    # Run Mind OpenRouter integration test (requires env)
```

### Frontend

```bash
bun run dev:frontend      # Start Vite dev server (from repo root)
bun run build:frontend    # Production build (from repo root)
# Or from apps/frontend/:
bun run dev
bun run build
```

### Environment Setup

```bash
cd apps/backend
cp .env.example .env
# Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY in .env
```

## PR Review Comment Workflow

When addressing GitHub PR feedback (including `chatgpt-codex-connector[bot]`):

1. **Fetch latest review comments with `gh api`**

```bash
gh pr status

# Example for PR 2 in this repo:
PR=2
review_id=$(gh api repos/Huvinesh-Rajendran-12/culture-engine/pulls/$PR/reviews \
  --jq 'map(select(.user.login=="chatgpt-codex-connector[bot]")) | sort_by(.submitted_at) | last | .id')

gh api repos/Huvinesh-Rajendran-12/culture-engine/pulls/$PR/reviews/$review_id/comments
```

2. **Validate each comment before editing**
- Re-read the referenced files.
- Reproduce the issue quickly (path resolution, runtime mode behavior, lifecycle/cleanup).
- Classify as valid / invalid and only change code for valid items.

3. **Apply minimal, compatible fixes**
- Prioritize P1 security/reliability comments.
- Preserve Mind API behavior and SSE event contract.
- For connector code specifically:
  - sanitize service names before file-path operations,
  - isolate connector load/instantiation failures,
  - close `httpx.AsyncClient` resources,
  - avoid connector auto-build loops for unresolved connector failures.

4. **Run backend tests**

```bash
cd apps/backend
uv run python -m pytest
```

5. **Commit, push, and trigger another review**

```bash
git add <files>
git commit -m "<focused message>"
git push
gh pr comment $PR --body "@codex review\n\nAddressed latest feedback in <commit>."
```

If a comment is not valid, respond in the PR with a concise technical rationale instead of adding churn.

## Architecture

Culture Engine is a monorepo with a FastAPI backend and a frontend client. The current focus is Mind-driven delegation: the user creates a persistent Mind, delegates tasks over SSE, and the system persists tasks, traces, and memory for iterative work.

### Request Flow

```
POST /api/minds/{mind_id}/delegate (SSE stream)
  └─ main.py handler (thin HTTP adapter)
       └─ MindService.delegate()
            └─ mind.pipeline.delegate_to_mind()  (raw dict stream)
                 ├─ load Mind profile + memory from SQLite
                 ├─ compose per-run tools (shared tools + memory + spawn_agent)
                 ├─ run_agent() streams tool/text/result events
                 └─ persist task status, trace events, and memory entries
            └─ EventStream wraps raw dicts → Event objects
```

All business logic lives in `MindService` (`mind/service.py`). HTTP handlers in `main.py` are thin adapters that catch domain exceptions (`MindNotFoundError`, `TaskNotFoundError`, `ValidationError`) and translate them to `HTTPException`. This makes the service layer reusable by future transports (WebSocket, MCP, CLI).

SSE events use a typed `Event` envelope: `{"id": ..., "type": ..., "seq": ..., "ts": ..., "trace_id": ..., "content": ...}`. The `type` and `content` fields are unchanged from the original format. The additional fields (`id`, `seq`, `ts`, `trace_id`) are additive. Common event types: `task_started`, `tool_registry`, `tool_use`, `tool_result`, `text`, `result`, `task_finished`, `error`.

### Key Packages (`src/backend/`)

| Package | Responsibility |
|---|---|
| `agents/base.py` | `run_agent()` — wraps `pi-agent-core`, translates events to SSE dicts |
| `agents/tools.py` | `DEFAULT_TOOL_NAMES` — central allowlist; file read/write/edit, run_command, search_apis, search_knowledge_base |
| `agents/api_catalog.py` | Searchable catalog of service actions |
| `agents/kb_search.py` | Keyword search over KB markdown sections |
| `mind/service.py` | `MindService` — protocol-agnostic service layer; all business logic for CRUD, feedback, delegation, tasks, drones, memory |
| `mind/events.py` | `Event` model (typed envelope) + `EventStream` wrapper that enriches raw pipeline dicts |
| `mind/exceptions.py` | Domain exceptions (`MindNotFoundError`, `TaskNotFoundError`, `ValidationError`) |
| `mind/schema.py` | `MindProfile`, `Task`, `MemoryEntry` models |
| `mind/config.py` | Centralized Mind runtime limits and defaults |
| `mind/pipeline.py` | `delegate_to_mind()` — task run orchestration and persistence |
| `mind/reasoning.py` | Mind system prompt composition + agent execution |
| `mind/tools/factory.py` | Per-run tool assembly for Mind execution |
| `mind/tools/primitives.py` | `memory_save`, `memory_search`, `spawn_agent` tools |
| `mind/store.py` | SQLite persistence for Mind profiles, tasks, and traces |
| `mind/memory.py` | SQLite FTS-backed memory retrieval and storage |

### Mind Data Model

Mind runs persist three linked records:

- `MindProfile` (identity + preferences + system prompt)
- `Task` (description, status, result summary, timestamps)
- `Task Trace` (SSE event stream captured per task)
- `MemoryEntry` (task results and explicit memory saves, searchable with FTS)

### Knowledge Base

- Location: `apps/backend/kb/{team}/*.md`
- Falls back to `kb/default/` for any file not found in the team folder
- Markdown files are split by `## Headings` into searchable `KBSection` objects
- Default KB: `onboarding_policy.md`, `roles.md`, `systems.md`

### Agent Tool Safety

- All file tools resolve paths through `_resolve_path()` to prevent workspace escape
- `run_command` runs in an isolated environment with a 30s timeout and 50 KB output cap
- Agent runs in a temp workspace directory, deleted on success

### Configuration

`src/backend/config.py` uses Pydantic `BaseSettings` (reads from `.env`):

| Setting | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Direct Anthropic access |
| `OPENROUTER_API_KEY` | OpenRouter proxy (recommended) |
| `ANTHROPIC_BASE_URL` | Override base URL (e.g., `https://openrouter.ai/api`) |
| `ANTHROPIC_AUTH_TOKEN` | Auth token for proxy |
| `DEFAULT_MODEL` | `haiku` (default), `sonnet`, or `opus` |

### Testing

- `tests/test_mind_api.py` — Mind API + SSE + persistence behavior
- `tests/test_mind_persistence.py` — SQLite store/memory persistence behavior
- `tests/test_integration_mind_openrouter.py` — OpenRouter integration for Mind delegation

Fastest sanity check:

```bash
uv run python -m pytest tests/test_mind_api.py tests/test_mind_persistence.py
```

### Frontend

Currently a frontend scaffold at `apps/frontend/`. The planned next phase is an SSE streaming UI centered on `/api/minds/{mind_id}/delegate` with task and memory inspection.
