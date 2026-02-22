# Culture Engine Backend

FastAPI backend for the Culture Engine path: persistent Mind delegation.

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
- `PATCH /api/minds/{mind_id}`
- `POST /api/minds/{mind_id}/feedback`
- `POST /api/minds/{mind_id}/delegate` (SSE)
- `GET /api/minds/{mind_id}/tasks`
- `GET /api/minds/{mind_id}/tasks/{task_id}`
- `GET /api/minds/{mind_id}/tasks/{task_id}/trace`
- `GET /api/minds/{mind_id}/memory`

## Mind execution model (simplified)

Mind identity includes:
- name/personality/preferences/system prompt
- structured charter (`mission`, `reason_for_existence`, principles, non-goals, reflection focus)

For each delegation run, system prompting includes:
- Mind identity + charter
- retrieved long-term memories
- runtime capability manifest (tool names + key limits)
- recent user feedback memories + autonomous mind insight memories

Learning loop:
- explicit user feedback can be stored via `POST /api/minds/{mind_id}/feedback`
- implicit preference signals are inferred from profile updates
- each run saves a `mind_insight` memory with adaptation notes

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
- Mind/task/memory persistence uses SQLite (WAL mode) with FTS5 full-text memory search

## Examples

- `examples/mind_delegate_example.py` — create a Mind and stream delegation SSE events

## Tests

Mind unit tests:

```bash
uv run python -m pytest tests/test_mind_api.py tests/test_mind_persistence.py
```

Mind OpenRouter integration test (opt-in):

```bash
export OPENROUTER_API_KEY=your_key
export RUN_OPENROUTER_INTEGRATION=1
export ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
uv run python -m pytest tests/test_integration_mind_openrouter.py
```

Without the integration env vars, OpenRouter tests are skipped by design.
