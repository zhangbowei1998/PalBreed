"""FastAPI entrypoint for agent-web (serves the frontend)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from pl_agent.agent.auth import make_user_store
from pl_agent.agent.auth.invites import (
    FileInviteStore,
    PostgresInviteStore,
    make_invite_store,
)
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
from pl_agent.agent.monitoring import InMemoryTraceStore, PostgresTraceStore
from pl_agent.agent.state.memory_store import InMemorySessionRepository

from .auth.routes import resolve_user_id_from_request, router as auth_router
from .monitoring_routes import router as monitoring_router


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

    # 邀请码存储
    invite_store = make_invite_store(settings.invite_store, settings.database_url)
    if isinstance(invite_store, PostgresInviteStore):
        await invite_store.connect()
    else:
        invite_store = FileInviteStore()

    # 监测：agent 对话 trace 存储（postgres 生产 / file 测试或无 DB 环境）
    if settings.trace_store == "postgres":
        try:
            trace_store = PostgresTraceStore(settings.database_url)
            await trace_store.connect()
        except Exception as exc:  # noqa: BLE001
            # 数据库不可用时降级到内存，避免服务因依赖 DB 而无法启动
            print(f"⚠️ trace_store postgres 连接失败，降级为内存: {exc}")
            trace_store = InMemoryTraceStore()
    else:
        trace_store = InMemoryTraceStore()

    app.state.settings = settings
    app.state.repository = repository
    app.state.llm = llm
    app.state.long_term_memory = long_term_memory
    app.state.user_store = user_store
    app.state.invite_store = invite_store
    app.state.trace_store = trace_store
    app.state.workflow = AgentWorkflow(
        settings=settings,
        repository=repository,
        client=client,
        llm=llm,
        long_term_memory=long_term_memory,
        trace_store=trace_store,
    )
    try:
        yield
    finally:
        if settings.long_term_store == "postgres":
            await long_term_memory.close()
        if isinstance(user_store, PostgresUserStore):
            await user_store.close()
        if isinstance(invite_store, PostgresInviteStore):
            await invite_store.close()
        await trace_store.close()


app = FastAPI(title="agent-web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(monitoring_router)


@app.get("/agent/pal-image/{pal_id}")
async def pal_image_proxy(pal_id: str):
    """帕鲁头像代理：从 paldb CDN 拉取图片返回（同源，规避 CORS，
    供前端配种树导出图片时读取像素）。"""
    import httpx as _httpx

    url = (
        "https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/"
        f"T_{pal_id}_icon_normal.webp"
    )
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="图片代理失败")
    if resp.status_code >= 400:
        raise HTTPException(status_code=404, detail="帕鲁图片不存在")
    media_type = resp.headers.get("content-type", "image/webp")
    return Response(
        content=resp.content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )



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
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
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


@app.post("/agent/chat/stream")
async def agent_chat_stream(body: ChatRequest, request: Request):
    """SSE 流式聊天：逐 token 推送回答文本（打字机效果）。"""
    if not body.session_id or not body.message.strip():
        raise HTTPException(
            status_code=400, detail="session_id and message are required"
        )

    workflow: AgentWorkflow = app.state.workflow
    user_id = resolve_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")

    async def event_stream():
        import asyncio
        import json

        q: asyncio.Queue = asyncio.Queue()
        result: dict = {"data": None, "error": None}

        async def on_text(delta: str) -> None:
            await q.put(("delta", delta))

        async def worker() -> None:
            try:
                with timer_ms() as metric:
                    data = await workflow.handle_chat(
                        ChatInput(
                            session_id=body.session_id,
                            message=body.message,
                            user_id=user_id,
                        ),
                        text_callback=on_text,
                    )
                data["meta"] = {
                    **data.get("meta", {}),
                    "action": "chat",
                    "latency_ms": metric["elapsed_ms"],
                    "user_id": user_id,
                }
                result["data"] = data
            except Exception as exc:  # noqa: BLE001
                result["error"] = str(exc)
            finally:
                await q.put(("__end__", None))

        task = asyncio.create_task(worker())
        try:
            while True:
                kind, payload = await q.get()
                if kind == "__end__":
                    break
                if kind == "delta":
                    yield f"data: {json.dumps({'type': 'delta', 'content': payload}, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

        if result["error"] is not None:
            yield f"data: {json.dumps({'type': 'error', 'message': result['error']}, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'data': result['data']}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/agent/action")
async def agent_action(body: ActionRequest, request: Request) -> dict:
    if not body.session_id or not body.action:
        raise HTTPException(
            status_code=400, detail="session_id and action are required"
        )

    valid_actions = {
        "confirm_target",
        "expand_parent",
        "select_parent_pair",
        "continue_from_parent",
    }
    if body.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"未知 action: {body.action}")

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
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
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
async def get_session(session_id: str, request: Request) -> dict:
    repository: InMemorySessionRepository = app.state.repository
    # 与 handle_chat/handle_action 一致的按用户隔离 key
    user_id = resolve_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    internal_key = f"u:{user_id or app.state.settings.default_user_key}:{session_id}"
    state = await repository.get(internal_key)
    if not state:
        raise HTTPException(status_code=404, detail="session not found")
    return {"success": True, "data": {"state_snapshot": state.model_dump()}}
