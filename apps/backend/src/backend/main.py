import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from .agents import generate_workflow
from .models import HealthResponse, WorkflowRequest
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

WORKFLOWS_DIR = Path(__file__).resolve().parents[3] / "workflows"
workflow_store = WorkflowStore(WORKFLOWS_DIR)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.post("/api/workflows/generate")
async def create_workflow_endpoint(request: WorkflowRequest):
    """Generate or modify a workflow from natural language description.

    Streams Server-Sent Events with agent progress:
    - text: Agent's reasoning and explanations
    - tool_use: Tools being called (Write, Bash, etc.)
    - workflow: The parsed workflow DAG
    - execution_report: Simulator execution results
    - result: Final result with cost/usage
    - error: Any errors encountered
    """
    # If modifying an existing workflow, load it
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
            session_id=request.session_id,
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
    """List all saved workflows for a team."""
    workflows = workflow_store.list_by_team(team)
    return [wf.model_dump() for wf in workflows]


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str, team: str = "default"):
    """Retrieve a specific workflow by ID."""
    wf = workflow_store.load(workflow_id, team=team)
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.model_dump()


@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, team: str = "default"):
    """Delete a workflow by ID."""
    deleted = workflow_store.delete(workflow_id, team=team)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"status": "deleted", "workflow_id": workflow_id}
