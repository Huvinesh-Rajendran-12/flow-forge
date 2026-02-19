# FlowForge Backend Quickstart

## 1) Install + Configure

```bash
uv sync
cp .env.example .env
```

Edit `.env` with one key option:

```bash
# Option A: OpenRouter (Anthropic-compatible)
OPENROUTER_API_KEY=your_key
ANTHROPIC_BASE_URL=https://openrouter.ai/api

# Option B: Direct Anthropic
# ANTHROPIC_API_KEY=your_key
```

Optional:

```bash
DEFAULT_MODEL=haiku
```

---

## 2) Start Backend

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open docs:
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 3) Culture Engine quick smoke test

### Create a Mind

```bash
curl -X POST http://localhost:8000/api/minds \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Orbit",
    "personality": "concise and practical",
    "preferences": {"tone": "direct"}
  }'
```

### Delegate task (SSE)

```bash
curl -N -X POST http://localhost:8000/api/minds/<mind_id>/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Summarize this week\'s engineering updates and draft a stakeholder note",
    "team": "default"
  }'
```

Common event types:
- `tool_registry`
- `text`
- `tool_use`
- `tool_result`
- `result`
- `error`

### Inspect persisted state

```bash
curl http://localhost:8000/api/minds/<mind_id>/tasks
curl http://localhost:8000/api/minds/<mind_id>/memory
```

---

## 4) Legacy workflow path (compatibility)

```bash
curl -N -X POST http://localhost:8000/api/workflows/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create an onboarding workflow for a new engineering hire",
    "context": {
      "employee_name": "Jane Doe",
      "role": "Software Engineer",
      "department": "Engineering"
    },
    "team": "default"
  }'
```

---

## 5) Troubleshooting

- **Auth errors**: verify `.env` keys and endpoint settings
- **Port conflict**: run with `--port 8001`
- **Dependency issues**: rerun `uv sync`
