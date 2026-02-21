# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
cd apps/backend

uv sync                                                    # Install/update dependencies
uv run uvicorn backend.main:app --reload --port 8000       # Start dev server
uv run pytest                                              # Run all tests
uv run pytest tests/test_workflow_engine_core.py           # Run a single test file
uv run python test_workflow_agent.py                       # Run deterministic tests (no API key needed)
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
review_id=$(gh api repos/Huvinesh-Rajendran-12/flow-forge/pulls/$PR/reviews \
  --jq 'map(select(.user.login=="chatgpt-codex-connector[bot]")) | sort_by(.submitted_at) | last | .id')

gh api repos/Huvinesh-Rajendran-12/flow-forge/pulls/$PR/reviews/$review_id/comments
```

2. **Validate each comment before editing**
- Re-read the referenced files.
- Reproduce the issue quickly (path resolution, runtime mode behavior, lifecycle/cleanup).
- Classify as valid / invalid and only change code for valid items.

3. **Apply minimal, compatible fixes**
- Prioritize P1 security/reliability comments.
- Keep legacy workflow compatibility and SSE event contract intact.
- For connector code specifically:
  - sanitize service names before file-path operations,
  - isolate connector load/instantiation failures,
  - close `httpx.AsyncClient` resources,
  - avoid connector auto-build work in `connector_mode="simulator"`.

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

FlowForge is a monorepo with a FastAPI backend and a React frontend. The core feature is AI-driven workflow generation: the user describes a process in natural language, the agent generates a JSON DAG, the system validates and simulates it, then persists successful workflows.

### Request Flow

```
POST /api/workflows/generate (SSE stream)
  └─ pipeline.generate_workflow()
       ├─ run_agent() → Claude writes workflow.json to temp workspace
       ├─ Parse JSON → validate against Workflow Pydantic model
       ├─ WorkflowExecutor.execute() → simulate against service stubs
       ├─ Self-correct on parse/execution failures (up to MAX_FIX_ATTEMPTS=2)
       └─ WorkflowStore.save() → persist to apps/workflows/{team}/
```

All responses are SSE events with shape `{"type": "...", "content": ...}`. Types: `text`, `tool_use`, `tool_result`, `workflow`, `execution_report`, `workflow_saved`, `result`, `error`, `workspace`.

### Key Packages (`src/backend/`)

| Package | Responsibility |
|---|---|
| `agents/base.py` | `run_agent()` — wraps `pi-agent-core`, translates events to SSE dicts |
| `agents/tools.py` | `DEFAULT_TOOL_NAMES` — central allowlist; file read/write/edit, run_command, search_apis, search_knowledge_base |
| `agents/api_catalog.py` | Searchable catalog of simulated service actions (HR, Google, Slack, Jira, GitHub) |
| `agents/kb_search.py` | Keyword search over KB markdown sections |
| `workflow/schema.py` | `Workflow`, `WorkflowNode`, `WorkflowEdge`, `NodeParameter` Pydantic models |
| `workflow/pipeline.py` | `generate_workflow()` — full orchestration loop with self-correction |
| `workflow/executor.py` | `WorkflowExecutor` — topological sort DAG runner with failure injection |
| `workflow/report.py` | `ExecutionReport` — trace + metrics + markdown output |
| `workflow/store.py` | `WorkflowStore` — file-based CRUD under `apps/workflows/{team}/` |
| `simulator/state.py` | `SimulatorState` (mutable shared state), `ExecutionTrace`, `TraceStep` |
| `simulator/services.py` | In-memory stubs: `HRService`, `GoogleService`, `SlackService`, `JiraService`, `GitHubService` |
| `simulator/failures.py` | `FailureConfig` + `FailureRule` for probabilistic failure injection |

### Workflow Data Model

```
Workflow
├── id, name, description, team, version
├── parameters: dict[str, Any]          # global inputs, e.g. {"employee_name": "Alice"}
├── nodes: list[WorkflowNode]
│   ├── id, name, description
│   ├── service: "hr"|"google"|"slack"|"jira"|"github"
│   ├── action: str                     # must match an ApiEntry in api_catalog.py
│   ├── actor: str                      # responsible role
│   ├── depends_on: list[str]           # upstream node IDs (defines DAG edges)
│   ├── parameters: list[NodeParameter] # values support template syntax (see below)
│   └── outputs: dict[str, str]         # output key → description
└── edges: list[WorkflowEdge]           # optional explicit edge metadata
```

**Templating in `NodeParameter.value`:**
- `{{param_name}}` — resolves to `workflow.parameters[param_name]`
- `{{node_id.output_key}}` — resolves to an upstream node's output at runtime

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

- `test_workflow_agent.py` — deterministic tests for schema, simulator, executor, store (no API key)
- `tests/test_workflow_engine_core.py` — engine unit tests
- `tests/test_workflow_generation.py` — requires API key (agent generation)
- `tests/test_integration_openrouter.py` — OpenRouter integration

Tests 1–4 in `test_workflow_agent.py` run without any API key and are the fastest sanity check.

### Frontend

Currently a React 19 + Vite + TypeScript scaffold at `apps/frontend/`. The planned next phase is an SSE streaming UI that consumes `/api/workflows/generate` and visualizes the DAG.
