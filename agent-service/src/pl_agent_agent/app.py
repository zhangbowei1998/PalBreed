"""FastAPI entrypoint for agent-service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .clients.breeding_api_client import BreedingApiClient
from .clients.errors import ClientError
from .config import Settings, load_settings
from .graph.guards import GuardViolation
from .graph.workflow import ActionInput, AgentWorkflow, ChatInput, StateConflictError
from .common.telemetry import timer_ms
from .state.memory_store import InMemorySessionRepository


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: dict = Field(default_factory=dict)


class ActionRequest(BaseModel):
    session_id: str
    action: str
    pal_id: str | None = None
    source_message_id: str | None = None
    mode: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = load_settings()
    repository = InMemorySessionRepository()
    client = BreedingApiClient(base_url=settings.breeding_api_base_url)
    app.state.settings = settings
    app.state.repository = repository
    app.state.workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=client,
    )
    yield


app = FastAPI(title="agent-service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/agent/chat")
async def agent_chat(body: ChatRequest) -> dict:
    if not body.session_id or not body.message.strip():
        raise HTTPException(
            status_code=400, detail="session_id and message are required"
        )

    workflow: AgentWorkflow = app.state.workflow
    try:
        with timer_ms() as metric:
            data = await workflow.handle_chat(
                ChatInput(session_id=body.session_id, message=body.message)
            )
        data["meta"] = {
            **data.get("meta", {}),
            "action": "chat",
            "latency_ms": metric["elapsed_ms"],
        }
        return {"success": True, "data": data}
    except ClientError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except StateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GuardViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/agent/action")
async def agent_action(body: ActionRequest) -> dict:
    if not body.session_id or not body.action:
        raise HTTPException(
            status_code=400, detail="session_id and action are required"
        )

    if body.action == "expand_parent" and (
        not body.pal_id or not body.source_message_id
    ):
        raise HTTPException(
            status_code=400,
            detail="expand_parent requires pal_id and source_message_id",
        )
    if body.action == "summarize_route" and not body.mode:
        raise HTTPException(status_code=400, detail="summarize_route requires mode")
    if body.action == "confirm_target" and not body.pal_id:
        raise HTTPException(status_code=400, detail="confirm_target requires pal_id")

    workflow: AgentWorkflow = app.state.workflow
    try:
        with timer_ms() as metric:
            data = await workflow.handle_action(
                ActionInput(
                    session_id=body.session_id,
                    action=body.action,
                    pal_id=body.pal_id,
                    source_message_id=body.source_message_id,
                    mode=body.mode,
                )
            )
        data["meta"] = {
            **data.get("meta", {}),
            "action": body.action,
            "latency_ms": metric["elapsed_ms"],
        }
        return {"success": True, "data": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ClientError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except StateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GuardViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/agent/session/{session_id}")
async def get_session(session_id: str) -> dict:
    repository: InMemorySessionRepository = app.state.repository
    state = await repository.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session not found")
    return {"success": True, "data": {"state_snapshot": state.model_dump()}}
