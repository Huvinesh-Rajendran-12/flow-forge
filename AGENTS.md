# AGENTS.md

This is the agent-facing map for the `flow-forge/` monorepo.

The project is currently in a **transition state**:
1. Legacy FlowForge workflow engine still exists and must keep working.
2. New **Culture Engine** (Mind/Drone architecture) is being built incrementally.

When in doubt, preserve compatibility and keep changes simple.

---

## 1) Monorepo Overview

- `apps/backend` — FastAPI + `pi-agent-core` runtime
- `apps/frontend` — React + Vite app (minimal)
- `apps/workflows` — persisted legacy workflow JSON artifacts

Root scripts (`package.json`):
- `dev:frontend`
- `dev:backend`
- `build:frontend`

---

## 2) Product Shape (Current)

### A) Culture Engine (new path)
Main concept: user delegates tasks to a persistent **Mind**.

Current backend endpoints:
- `POST /api/minds`
- `GET /api/minds/{id}`
- `POST /api/minds/{id}/delegate` (SSE)
- `GET /api/minds/{id}/tasks`
- `GET /api/minds/{id}/tasks/{task_id}`
- `GET /api/minds/{id}/memory`

Phase 1 scope intentionally simplified:
- single-path orchestration (no automatic sub-agent splitting)
- SQLite (WAL mode) persistence with FTS5 memory search
- prompt composition from identity + memory

### B) Legacy FlowForge (compat path)
Still exposed and supported:
- `POST /api/workflows/generate` (SSE)
- workflow CRUD endpoints

---

## 3) Backend Architecture (`apps/backend/src/backend`)

### Stable shared layer
- `agents/base.py` — shared `run_agent(...)` wrapper over `pi-agent-core`
- `agents/anthropic_stream.py` — Anthropic/OpenRouter stream adapter
- SSE event contract (`type` + `content`) must remain compatible

### Culture Engine layer
- `mind/schema.py` — Mind/Drone/Task/Memory models
- `mind/database.py` — SQLite schema, WAL mode init, FTS5 virtual table + triggers
- `mind/identity.py` — Mind creation helpers
- `mind/memory.py` — SQLite-backed memory manager with FTS5 search
- `mind/store.py` — SQLite-backed profile + task persistence
- `mind/reasoning.py` — dynamic system prompt + agent execution
- `mind/orchestrator.py` — simplified single-run orchestrator
- `mind/pipeline.py` — delegate flow (load memory → execute → persist)
- `mind/tools/factory.py` — plain per-run tool list assembly
- `mind/tools/primitives.py` — Mind-specific primitives (`memory_save`, `memory_search`, `spawn_agent`)

### Legacy workflow layer
- `workflow/` — schema/executor/pipeline/store/report
- `simulator/` — fake services + failure injection
- `agents/api_catalog.py`, `agents/kb_search.py`, `agents/tools.py`

---

## 4) Simplification Rules (Important)

1. Prefer the smallest vertical slice that works.
2. Avoid speculative abstractions.
3. Keep orchestration explicit; avoid hidden magic.
4. Create directories only on write paths (not on reads).
5. Keep temporary workspace lifecycle automatic and bounded.
6. Preserve backward compatibility unless explicitly removed.

---

## 5) Tooling Philosophy

Current shared tool allowlist remains in:
- `agents/tools.py` → `DEFAULT_TOOL_NAMES`

Guideline:
- composition/prompting first,
- new tools only when necessary.

Culture Engine Phase 2 was intentionally simplified:
- no runtime tool registration API yet,
- no persistent dynamic tool store yet,
- no separate tool-registry abstraction.

Current Mind tool assembly is a plain list built per run:
- legacy composable tools from `agents/tools.py`
- `memory_save`
- `memory_search`
- `spawn_agent` (explicit sub-agent delegation)

---

## 6) Config & Environment

Backend env (`apps/backend/.env`):
- `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`
- optional `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`
- `DEFAULT_MODEL`

Run backend:
```bash
cd apps/backend
uv sync
uv run uvicorn backend.main:app --reload --port 8100
```

Run frontend:
```bash
cd apps/frontend
npm install
npm run dev
```

---

## 7) Contributor Conventions

- Keep tool names in snake_case.
- Maintain workspace path safety for file tools.
- Preserve SSE message compatibility.
- Keep docs aligned with implementation in `src/backend/`.
- Mark legacy codepaths clearly with `LEGACY` comments/docstrings.

---

## 8) PR Review Comment Handling (Codex/GitHub bots/humans)

When a PR gets review comments, follow this flow:

1. **Fetch the latest comments first**
   - Identify the current PR: `gh pr status`
   - Pull latest bot reviews/comments with `gh api` (prefer structured JSON + `jq` over manual UI scanning).

2. **Validate each comment against current HEAD**
   - Read the referenced files before changing anything.
   - Reproduce critical claims with quick checks (e.g., path resolution, mode flags, resource lifecycle).
   - Mark each comment as: **valid / partially valid / not valid** with a short reason.

3. **Fix only what is valid, with minimal compatible changes**
   - Prioritize **P1 security/reliability** items first.
   - Preserve backward compatibility and SSE contracts.
   - Keep fixes explicit (no speculative abstractions).

4. **Patterns we now enforce in connector code**
   - Validate untrusted identifiers before file-path usage (e.g., service names for `custom_connectors`).
   - Isolate dynamic connector instantiation failures so one bad connector does not break unrelated workflows.
   - Close `httpx.AsyncClient` instances after each workflow run.
   - Skip connector auto-build loops when `connector_mode == "simulator"`.

5. **Verify before shipping**
   - Run backend tests: `cd apps/backend && uv run python -m pytest`
   - Ensure working tree is clean except intended changes.

6. **Ship and request re-review**
   - Commit with a focused message.
   - Push branch.
   - Tag Codex again on the PR, e.g.:
     - `gh pr comment <pr_number> --body "@codex review\n\nAddressed latest feedback in <commit>."`

If feedback is not valid, do **not** churn code; reply on PR with concise technical rationale.

---

## 9) Near-term Plan

1. Keep Phase 1/2 core stable (Mind + memory + explicit `spawn_agent`).
2. Add focused tests for Mind core, delegation pipeline, and tool events.
3. Improve sub-agent orchestration quality before adding new abstractions.
4. Revisit runtime tool registration only after clear product need appears.
