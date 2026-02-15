# FlowForge

FlowForge is a monorepo for building AI-assisted workflow automation.

It currently includes:
- a **backend** unified agent that can design/modify/validate/execute workflow DAGs,
- a **frontend** React app (minimal scaffold, ready for streaming UI integration).

---

## Monorepo Structure

| Directory | Stack | Description |
|---|---|---|
| `apps/backend` | Python, FastAPI, pi-agent-core | Unified workflow agent API (SSE streaming) |
| `apps/frontend` | React, Vite, TypeScript | Web client |
| `apps/workflows` | JSON files | Persisted workflow versions by team |

---

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+

### 1) Run Backend

```bash
cd apps/backend
uv sync
cp .env.example .env
```

Set one auth option in `apps/backend/.env`:

```bash
# Option A (recommended): OpenRouter (Anthropic-compatible)
OPENROUTER_API_KEY=your_key
ANTHROPIC_BASE_URL=https://openrouter.ai/api

# Option B: Direct Anthropic
# ANTHROPIC_API_KEY=your_key
```

Start API:

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### 2) Run Frontend

```bash
cd apps/frontend
npm install
npm run dev
```

---

## Backend Highlights

The backend uses a **unified FlowForge agent** that can:
1. interpret user workflow requests,
2. write/update `workflow.json`,
3. validate schema,
4. execute DAG in simulator,
5. self-correct on parse/execution failures.

SSE endpoint:

- `POST /api/workflows/generate`

Common stream event types:
- `text`
- `tool_use`
- `tool_result`
- `workflow`
- `execution_report`
- `workflow_saved`
- `result`
- `error`
- `workspace`

### Minimal composable default tools

FlowForge intentionally keeps tools small and composable:
- `read_file`
- `write_file`
- `edit_file`
- `search_apis`
- `search_knowledge_base`

Source of truth: `apps/backend/src/backend/agents/tools.py` (`DEFAULT_TOOL_NAMES`).

---

## Development Scripts (root)

```bash
bun run dev:frontend
bun run dev:backend
bun run build:frontend
```

---

## Testing

From backend app:

```bash
cd apps/backend
uv sync
uv run pytest
```

Test files currently include:
- `test_workflow_agent.py`
- `test_workflow_e2e.py`
- `tests/test_workflow_engine_core.py`
- `tests/test_workflow_generation.py`
- `tests/test_integration_openrouter.py`

---

## Docs

- Backend details: `apps/backend/README.md`
- Backend quickstart: `apps/backend/QUICKSTART.md`
- Agent/contributor map: `AGENTS.md`

---

## License

MIT
