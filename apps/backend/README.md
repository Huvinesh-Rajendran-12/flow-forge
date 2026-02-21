# FlowForge Backend (Culture Engine transition)

FastAPI backend for two parallel paths:

1. **Culture Engine (current direction)** — persistent Mind delegation.
2. **Legacy FlowForge workflows** — DAG generation/execution kept for compatibility.

## Tech Stack

- Python 3.11+
- FastAPI
- pi-agent-core
- Anthropic/OpenRouter (Anthropic-compatible API)

## Setup

```bash
uv sync
cp .env.example .env
```

Set one auth option in `.env`:

- `OPENROUTER_API_KEY=...` (recommended)
- or `ANTHROPIC_API_KEY=...`

Optional:

- `ANTHROPIC_BASE_URL=https://openrouter.ai/api`
- `ANTHROPIC_AUTH_TOKEN=...`
- `DEFAULT_MODEL=haiku`

## Run API

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8100
```

- API: `http://localhost:8100`
- Swagger: `http://localhost:8100/docs`

## Endpoints

### Health
- `GET /api/health`

### Culture Engine (Mind)
- `POST /api/minds`
- `GET /api/minds`
- `GET /api/minds/{mind_id}`
- `POST /api/minds/{mind_id}/delegate` (SSE)
- `GET /api/minds/{mind_id}/tasks`
- `GET /api/minds/{mind_id}/tasks/{task_id}`
- `GET /api/minds/{mind_id}/tasks/{task_id}/trace`
- `GET /api/minds/{mind_id}/memory`

### Legacy workflow endpoints
- `POST /api/workflows/generate` (SSE)
- `GET /api/workflows`
- `GET /api/workflows/{workflow_id}`
- `DELETE /api/workflows/{workflow_id}`

## Mind execution model (simplified)

Current per-run toolset:
- shared composable tools from `src/backend/agents/tools.py`
- `memory_save`
- `memory_search`
- `spawn_agent`

Notes:
- no runtime tool registration API yet
- no persistent dynamic tool store yet
- explicit `spawn_agent` delegation only (no implicit auto-splitting)
- guardrails: capped spawned sub-agent calls, capped sub-agent turns, capped event volume per run
- Mind/task/memory persistence uses atomic JSON writes with a simple file lock

## Examples

- `examples/workflow_example.py` — legacy workflow SSE client
- `examples/interactive_workflow_generator.py` — interactive CLI debugging flow

## Tests

Current tests:
- `tests/test_workflow_engine_core.py`
- `tests/test_workflow_generation.py`
- `tests/test_integration_openrouter.py`
- `tests/test_integration_mind_openrouter.py`
- `tests/test_mind_api.py`
- `tests/test_mind_persistence.py`

Run:

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```
