# Culture Engine Backend Quickstart

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
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8100
```

Open docs:
- Swagger: `http://localhost:8100/docs`
- ReDoc: `http://localhost:8100/redoc`

---

## 3) Culture Engine quick smoke test

### Create a Mind

```bash
curl -X POST http://localhost:8100/api/minds \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Orbit",
    "personality": "concise and practical",
    "preferences": {"tone": "direct"},
    "charter": {
      "mission": "Help design and evolve the Mind platform with the user.",
      "reason_for_existence": "Provide a persistent operator that can assess capabilities and execute safely."
    }
  }'
```

### Delegate task (SSE)

```bash
curl -N -X POST http://localhost:8100/api/minds/<mind_id>/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Summarize this week\'s engineering updates and draft a stakeholder note",
    "team": "default"
  }'
```

### Update Mind charter/profile (partial)

```bash
curl -X PATCH http://localhost:8100/api/minds/<mind_id> \
  -H "Content-Type: application/json" \
  -d '{
    "personality": "strategic and candid",
    "charter": {
      "mission": "Continuously assess and improve Mind capabilities with the user.",
      "reflection_focus": [
        "Identify the biggest current capability gap",
        "Recommend the next highest-leverage upgrade"
      ]
    }
  }'
```

### Send user feedback to the Mind

```bash
curl -X POST http://localhost:8100/api/minds/<mind_id>/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Default to acting on reversible ambiguity and only ask on high-risk operations.",
    "rating": 5,
    "tags": ["autonomy", "risk_tolerance"]
  }'
```

Notes:
- Explicit feedback is optional. The Mind also infers implicit preference signals from profile updates.
- After each run, the Mind stores an autonomous `mind_insight` memory for future adaptation.

Common event types:
- `tool_registry`
- `text`
- `tool_use`
- `tool_result`
- `result`
- `error`

### Inspect persisted state

```bash
curl http://localhost:8100/api/minds
curl http://localhost:8100/api/minds/<mind_id>/tasks
curl http://localhost:8100/api/minds/<mind_id>/memory
curl http://localhost:8100/api/minds/<mind_id>/tasks/<task_id>/trace
```

---

## 4) Troubleshooting

- **Auth errors**: verify `.env` keys and endpoint settings
- **Port conflict**: run with `--port 8001`
- **Dependency issues**: rerun `uv sync`
