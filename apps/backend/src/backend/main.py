import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .mind.identity import create_mind_identity
from .mind.memory import MemoryManager
from .mind.pipeline import delegate_to_mind
from .mind.store import MindStore
from .models import DelegateTaskRequest, HealthResponse, MindCreateRequest, WorkflowRequest
from .workflow.pipeline import generate_workflow
from .workflow.store import WorkflowStore

load_dotenv()

app = FastAPI(
    title="FlowForge API",
    description="AI agents that design, build, and run workflows from natural language",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = ROOT_DIR / "workflows"

# Culture Engine storage (preferred)
CULTURE_DATA_DIR = ROOT_DIR / "culture"
# Backward-compatible fallback for existing local data
LEGACY_MIND_DATA_DIR = ROOT_DIR / "mind"
if not CULTURE_DATA_DIR.exists() and LEGACY_MIND_DATA_DIR.exists():
    CULTURE_DATA_DIR = LEGACY_MIND_DATA_DIR

workflow_store = WorkflowStore(WORKFLOWS_DIR)
mind_store = MindStore(CULTURE_DATA_DIR)
memory_manager = MemoryManager(CULTURE_DATA_DIR / "memory")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


# --- Legacy FlowForge workflow endpoints (kept for compatibility) ---

@app.post("/api/workflows/generate")
async def create_workflow_endpoint(request: WorkflowRequest):
    """LEGACY: Generate or modify a workflow from natural language description."""
    existing_workflow = None
    if request.workflow_id:
        existing_workflow = workflow_store.load(request.workflow_id, team=request.team)
        if existing_workflow is None:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow '{request.workflow_id}' not found for team '{request.team}'",
            )

    async def event_stream():
        async for message in generate_workflow(
            description=request.description,
            context=request.context,
            team=request.team,
            existing_workflow=existing_workflow,
            workflow_store=workflow_store,
        ):
            yield f"data: {json.dumps(message)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/workflows")
def list_workflows(team: str = "default"):
    workflows = workflow_store.list_by_team(team)
    return [wf.model_dump() for wf in workflows]


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str, team: str = "default"):
    wf = workflow_store.load(workflow_id, team=team)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.model_dump()


@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, team: str = "default"):
    deleted = workflow_store.delete(workflow_id, team=team)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "deleted", "workflow_id": workflow_id}


# --- Culture Engine Mind endpoints ---

@app.post("/api/minds")
def create_mind(request: MindCreateRequest):
    mind = create_mind_identity(
        name=request.name,
        personality=request.personality,
        preferences=request.preferences,
        system_prompt=request.system_prompt,
    )
    mind_store.save_mind(mind)
    return mind.model_dump(mode="json")


@app.get("/api/minds/{mind_id}")
def get_mind(mind_id: str):
    mind = mind_store.load_mind(mind_id)
    if mind is None:
        raise HTTPException(status_code=404, detail="Mind not found")
    return mind.model_dump(mode="json")


@app.post("/api/minds/{mind_id}/delegate")
async def delegate_task(mind_id: str, request: DelegateTaskRequest):
    async def event_stream():
        async for event in delegate_to_mind(
            mind_store=mind_store,
            memory_manager=memory_manager,
            mind_id=mind_id,
            description=request.description,
            team=request.team,
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/minds/{mind_id}/tasks")
def list_mind_tasks(mind_id: str):
    mind = mind_store.load_mind(mind_id)
    if mind is None:
        raise HTTPException(status_code=404, detail="Mind not found")
    return [task.model_dump(mode="json") for task in mind_store.list_tasks(mind_id)]


@app.get("/api/minds/{mind_id}/tasks/{task_id}")
def get_mind_task(mind_id: str, task_id: str):
    task = mind_store.load_task(mind_id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump(mode="json")


@app.get("/api/minds/{mind_id}/memory")
def list_mind_memory(mind_id: str, category: str | None = None):
    mind = mind_store.load_mind(mind_id)
    if mind is None:
        raise HTTPException(status_code=404, detail="Mind not found")
    return [m.model_dump(mode="json") for m in memory_manager.list_all(mind_id, category=category)]
