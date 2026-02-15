# AGENTS.md

This document is the **agent-facing map** of the FlowForge monorepo.
It explains what exists today, where to make changes, and what principles to keep.

> Repository root: `flow-forge/`

---

## 1) Monorepo Overview

FlowForge is a two-app repo:

- `apps/backend` — Python/FastAPI + `pi-agent-core` runtime for workflow generation/execution
- `apps/frontend` — React + Vite web app

There is also:

- `apps/workflows` — persisted workflow JSON artifacts

Root scripts (`package.json`):

- `dev:frontend` → run frontend dev server
- `dev:backend` → run backend API
- `build:frontend` → build frontend

---

## 2) Current Product Shape

FlowForge accepts natural-language workflow requests, has an LLM agent produce/update `workflow.json`, validates it, executes it in a simulator, and self-corrects on failures.

Streaming responses from backend use SSE event objects like:

- `text`
- `tool_use`
- `tool_result`
- `workflow`
- `execution_report`
- `workflow_saved`
- `result`
- `error`
- `workspace`

---

## 3) Backend Architecture (`apps/backend`)

### API entrypoint

- `src/backend/main.py`
  - FastAPI app
  - `/api/workflows/generate` (SSE)
  - workflow CRUD endpoints (`list/get/delete`)

### Agent layer

- `src/backend/agents/workflow_agent.py`
  - **Unified FlowForge agent orchestration**
  - Builds initial prompt
  - Calls `run_agent(...)`
  - Parses/validates `workflow.json`
  - Executes simulator
  - Runs fix attempts when parse/execution fails

- `src/backend/agents/base.py`
  - Generic `run_agent(...)` wrapper over `pi-agent-core`
  - Model selection + event translation into SSE payloads

- `src/backend/agents/tools.py`
  - Tool definitions + implementations
  - Workspace path safety checks
  - Exposes a **minimal composable toolset**

- `src/backend/agents/anthropic_stream.py`
  - Anthropic/OpenRouter stream adapter used by backend runtime

- `src/backend/agents/api_catalog.py`
  - Static searchable catalog of simulated service actions

- `src/backend/agents/kb_search.py`
  - Search over markdown KB sections (`apps/backend/kb/...`)

### Workflow engine

- `src/backend/workflow/schema.py` — Pydantic workflow DAG schema
- `src/backend/workflow/executor.py` — topological DAG executor + parameter substitution
- `src/backend/workflow/report.py` — execution report model + markdown output
- `src/backend/workflow/store.py` — JSON file persistence per team/version

### Simulator

- `src/backend/simulator/services.py` — fake service APIs
- `src/backend/simulator/failures.py` — injectable failure rules
- `src/backend/simulator/state.py` — execution trace/state

### Examples

- `apps/backend/examples/interactive_workflow_generator.py`
  - interactive CLI (core-style) for debugging/iterating with agent
- `apps/backend/examples/workflow_example.py`
  - simple SSE client example against backend endpoint

### Tests

- legacy top-level tests:
  - `test_workflow_agent.py`
  - `test_workflow_e2e.py`
- newer suite:
  - `tests/test_workflow_engine_core.py`
  - `tests/test_workflow_generation.py`
  - `tests/test_integration_openrouter.py`

---

## 4) Frontend Architecture (`apps/frontend`)

Current frontend is intentionally minimal:

- `src/main.tsx` bootstraps React app
- `src/App.tsx` renders a placeholder title

Build tooling:

- Vite + TypeScript + React 19
- Scripts: `dev`, `build`, `preview`

No complex state/data layer is present yet.

---

## 5) Tooling Philosophy (Important)

FlowForge currently favors a **minimal agent toolset** so the model learns to compose primitives.

Source of truth:

- `src/backend/agents/tools.py` → `DEFAULT_TOOL_NAMES`

Current default tools:

1. `read_file`
2. `write_file`
3. `edit_file`
4. `search_apis`
5. `search_knowledge_base`

Guideline:

- Prefer adding capability through composition/prompting first.
- Add new tools only when composition is insufficient.

---

## 6) Config & Environment

Backend env (`apps/backend/.env`):

- `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`
- optional Anthropic-compatible endpoint:
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_AUTH_TOKEN`
- `DEFAULT_MODEL`

Run backend:

```bash
cd apps/backend
uv sync
uv run uvicorn backend.main:app --reload --port 8000
```

Run frontend:

```bash
cd apps/frontend
npm install
npm run dev
```

---

## 7) Agent/Contributor Conventions

When editing FlowForge:

1. Keep tool names in snake_case and aligned with `pi-agent-core` examples.
2. Keep `DEFAULT_TOOL_NAMES` as central allowlist source.
3. Maintain workspace path safety (`_resolve_path`) for file tools.
4. Preserve SSE message compatibility (`type` + `content` objects).
5. Validate workflow JSON with schema before execution.
6. Keep execution self-correction loop intact unless intentionally redesigning behavior.

---

## 8) Known Drift / Documentation Notes

Some older docs in `apps/backend/README.md` and `QUICKSTART.md` mention earlier "code generation" phases and older tool names.

**Source of truth is implementation under `src/backend/`** (especially `agents/workflow_agent.py` and `agents/tools.py`).

---

## 9) Suggested Next Simplifications

- Centralize model-id resolution for API + examples in one module
- Reduce duplicated tests / clarify which test suite is canonical
- Update stale backend docs to match unified-agent architecture
- Add frontend workflow streaming UI once backend contract is stable
