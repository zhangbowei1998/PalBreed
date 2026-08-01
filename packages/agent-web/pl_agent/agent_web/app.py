"""FastAPI entrypoint for agent-web (serves the frontend)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pl_agent.agent.auth import make_user_store
from pl_agent.agent.auth.postgres import PostgresUserStore
from pl_agent.agent.clients.breeding_api_client import BreedingApiClient
from pl_agent.agent.clients.errors import ClientError
from pl_agent.agent.common.telemetry import timer_ms
from pl_agent.agent.config import Settings, load_settings
from pl_agent.agent.graph.guards import GuardViolation
from pl_agent.agent.graph.workflow import (
    ActionInput,
    AgentWorkflow,
    ChatInput,
    StateConflictError,
)
from pl_agent.agent.llm import LLMConfig, create_llm_client
from pl_agent.agent.memory.long_term import LongTermMemory, LongTermMemoryStore
from pl_agent.agent.memory.postgres import PostgresLongTermMemory
from pl_agent.agent.state.memory_store import InMemorySessionRepository

from .auth.routes import resolve_user_id_from_request, router as auth_router


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: dict = Field(default_factory=dict)


class ActionRequest(BaseModel):
    session_id: str
    action: str
    pal_id: str | None = None
    child_pal_id: str | None = None
    pair_index: int | None = None
    source_message_id: str | None = None
    mode: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = load_settings()
    repository = InMemorySessionRepository()
    client = BreedingApiClient(base_url=settings.breeding_api_base_url)

    llm = None
    if settings.llm_enabled:
        llm = create_llm_client(
            LLMConfig(
                provider=settings.llm_provider,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout_s=settings.llm_timeout_s,
            )
        )

    long_term_memory: LongTermMemoryStore
    if settings.long_term_store == "postgres":
        long_term_memory = PostgresLongTermMemory(settings.database_url)
        await long_term_memory.connect()
    else:
        long_term_memory = LongTermMemory()

    user_store = make_user_store(settings.user_store, settings.database_url)
    if isinstance(user_store, PostgresUserStore):
        await user_store.connect()

    app.state.settings = settings
    app.state.repository = repository
    app.state.llm = llm
    app.state.long_term_memory = long_term_memory
    app.state.user_store = user_store
    app.state.workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=client,
        llm=llm,
        long_term_memory=long_term_memory,
    )
    try:
        yield
    finally:
        if settings.long_term_store == "postgres":
            await long_term_memory.close()
        if isinstance(user_store, PostgresUserStore):
            await user_store.close()


app = FastAPI(title="agent-web", lifespan=lifespan)

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

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.post("/agent/chat")
async def agent_chat(body: ChatRequest, request: Request) -> dict:
    if not body.session_id or not body.message.strip():
        raise HTTPException(
            status_code=400, detail="session_id and message are required"
        )

    workflow: AgentWorkflow = app.state.workflow
    user_id = resolve_user_id_from_request(request)
    try:
        with timer_ms() as metric:
            data = await workflow.handle_chat(
                ChatInput(
                    session_id=body.session_id,
                    message=body.message,
                    user_id=user_id,
                )
            )
        data["meta"] = {
            **data.get("meta", {}),
            "action": "chat",
            "latency_ms": metric["elapsed_ms"],
            "user_id": user_id,
        }
        return {"success": True, "data": data}
    except ClientError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except StateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GuardViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/agent/action")
async def agent_action(body: ActionRequest, request: Request) -> dict:
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
    if body.action == "confirm_target" and not body.pal_id:
        raise HTTPException(status_code=400, detail="confirm_target requires pal_id")
    if body.action == "select_parent_pair" and (
        not body.child_pal_id or body.pair_index is None
    ):
        raise HTTPException(
            status_code=400,
            detail="select_parent_pair requires child_pal_id and pair_index",
        )
    if body.action == "continue_from_parent" and not body.pal_id:
        raise HTTPException(
            status_code=400,
            detail="continue_from_parent requires pal_id",
        )

    workflow: AgentWorkflow = app.state.workflow
    user_id = resolve_user_id_from_request(request)
    try:
        with timer_ms() as metric:
            data = await workflow.handle_action(
                ActionInput(
                    session_id=body.session_id,
                    action=body.action,
                    pal_id=body.pal_id,
                    child_pal_id=body.child_pal_id,
                    pair_index=body.pair_index,
                    source_message_id=body.source_message_id,
                    mode=body.mode,
                    user_id=user_id,
                )
            )
        data["meta"] = {
            **data.get("meta", {}),
            "action": body.action,
            "latency_ms": metric["elapsed_ms"],
            "user_id": user_id,
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
