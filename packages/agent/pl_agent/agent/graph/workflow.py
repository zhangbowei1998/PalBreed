"""Agent workflow entrypoints."""

from __future__ import annotations

from dataclasses import dataclass

from ..clients.breeding_api_client import BreedingApiClient
from ..common.constants import (
    ACTION_CONFIRM_TARGET,
    ACTION_CONTINUE_FROM_PARENT,
    ACTION_EXPAND_PARENT,
    ACTION_SELECT_PARENT_PAIR,
)
from ..common.telemetry import timer_ms
from ..config import Settings
from ..intent import Intent, IntentRecognizer
from ..interaction.click_protocol import parse_expand_fallback
from ..interaction.presenter import build_response
from ..llm import LLMClient
from ..memory.compress import summarize_history
from ..memory.long_term import (
    LongTermMemory,
    LongTermMemoryStore,
    MemoryFact,
    extract_owned_facts,
    extract_preference_facts,
)
from ..monitoring.models import AgentTrace, TraceStore
from ..state.memory_store import InMemorySessionRepository
from ..state.models import ChatTurn, ClickEvent, SessionState
from ..tools import ToolRegistry, build_breeding_tools
from .agent_loop import AgentLoop, AgentLoopResult
from .guards import GuardViolation, ensure_expand_allowed
from .nodes import (
    build_reused_node_response,
    query_parents_and_record,
    resolve_top_candidates,
    select_parent_pair,
)

_SYSTEM_PROMPT = """\
你是幻兽帕鲁（Palworld）配种助手。用户会问你关于帕鲁的问题，例如：
- 某只帕鲁怎么配种 / 父母是谁（必须调用 query_parent_pairs 获取精确结果）
- 某工种（手工、烧火、采矿、浇水、伐木、搬运等）最高/最强的帕鲁
- 某只帕鲁的基础信息
- 数据库统计（一共有多少只帕鲁）

规则：
1. 配种方案是固定公式计算的精确数据，绝对不要自行推算，必须调用工具获取。
2. 帕鲁名不确定时，可以先用 resolve_pal 解析。
3. 用自然、简洁的中文回答用户，可以适当归纳工具返回的结果。
4. 如果工具返回错误（例如找不到帕鲁），如实告诉用户并给出建议。
5. 【重要】用户可能省略主语，例如只说"怎么配种"、"那它呢"、"换一个"。
   必须结合最近对话推断意图：若上一条对话提到了某只帕鲁或某个工种，
   就把当前问题理解为针对该对象的追问。不要反问用户"你指哪只"。
6. 追问目标帕鲁时（如"磐甲龙怎么配种"），调用 query_parent_pairs 查询并回答。
"""


class StateConflictError(Exception):
    pass


@dataclass
class ChatInput:
    session_id: str
    message: str
    user_id: str | None = None


@dataclass
class ActionInput:
    session_id: str
    action: str
    pal_id: str | None = None
    child_pal_id: str | None = None
    pair_index: int | None = None
    source_message_id: str | None = None
    mode: str | None = None
    user_id: str | None = None


class AgentWorkflow:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemorySessionRepository,
        client: BreedingApiClient,
        llm: LLMClient | None = None,
        long_term_memory: LongTermMemoryStore | None = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._client = client
        self._llm = llm
        self._long_term_memory = long_term_memory or LongTermMemory()
        self._trace_store = trace_store
        self._recognizer = IntentRecognizer(llm=llm, breeding_api=client)
        self._tool_registry = ToolRegistry(
            build_breeding_tools(client, top_n_default=settings.top_candidates)
        )
        self._agent_loop = None
        if llm is not None:
            self._agent_loop = AgentLoop(
                llm=llm,
                registry=self._tool_registry,
                system_prompt=_SYSTEM_PROMPT,
            )

    def _user_key(self, session_id: str, user_id: str | None = None) -> str:
        # 有登录用户时按用户隔离长期记忆；匿名会话退回 default。
        # 前端登录注册上线后，把这里的 user_id 换成登录态即可。
        return user_id or self._settings.default_user_key

    async def _load_or_create_state(self, session_id: str) -> SessionState:
        state = await self._repository.get(session_id)
        if state:
            return state
        state = SessionState(session_id=session_id)
        state.limits.max_depth = self._settings.max_depth
        state.limits.max_nodes = self._settings.max_nodes
        return await self._repository.save(session_id, state)

    async def handle_chat(self, data: ChatInput) -> dict:
        state = await self._load_or_create_state(data.session_id)

        if self._agent_loop is not None:
            return await self._handle_llm_chat(
                data.session_id, state, data.message, user_id=data.user_id
            )

        fallback_expand = parse_expand_fallback(data.message)
        if fallback_expand:
            return await self.handle_action(
                ActionInput(
                    session_id=data.session_id,
                    action=ACTION_EXPAND_PARENT,
                    pal_id=fallback_expand,
                    source_message_id="fallback_command",
                )
            )

        intent = await self._recognizer.recognize(data.message)

        if intent.is_top_suitability():
            work_type = intent.work_type or "handiwork"
            messages, actions = await resolve_top_candidates(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                top_n=self._settings.top_candidates,
                work_type=work_type,
            )
            state = await self._repository.get(data.session_id) or state
            if state.target_pal:
                pm, pa = await query_parents_and_record(
                    session_id=data.session_id,
                    state=state,
                    repository=self._repository,
                    client=self._client,
                    pal_id=state.target_pal,
                )
                messages.extend(pm)
                actions.extend(pa)
                state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if intent.is_expand_pal() and intent.pal_name:
            return await self._handle_expand_pal(
                data.session_id, state, intent.pal_name
            )

        if intent.intent == Intent.PAL_STATS:
            return await self._handle_pal_stats(data.session_id, state)

        return build_response(
            messages=[self._general_reply(data.message, intent.reason)],
            actions=[],
            state=state,
        )

    async def _handle_llm_chat(
        self,
        session_id: str,
        state: SessionState,
        message: str,
        user_id: str | None = None,
    ) -> dict:
        assert self._agent_loop is not None

        # 短期记忆：最近 N 轮对话
        max_turns = self._settings.short_term_max_turns
        recent = state.chat_history[-max_turns:]
        history = [{"role": turn.role, "content": turn.content} for turn in recent]

        # 长期记忆：读取该用户持久事实，注入 system prompt
        user_key = self._user_key(session_id, user_id)
        loaded_facts = await self._long_term_memory.load(user_key)
        long_term_facts = [self._format_fact(fact) for fact in loaded_facts]

        # 上下文压缩：早期对话的摘要（若之前压缩过）
        history_summary = state.history_summary or None

        with timer_ms() as metric:
            try:
                result = await self._agent_loop.run(
                    message,
                    history=history,
                    long_term_facts=long_term_facts,
                    history_summary=history_summary,
                )
                reply = result.content
            except Exception as exc:  # noqa: BLE001
                reply = f"LLM 处理失败：{exc}"
                result = None

        # 监测：组装本次对话 trace 并记录
        await self._record_trace(
            session_id=session_id,
            user_key=user_key,
            user_message=message,
            reply=reply,
            result=result,
            latency_ms=metric["elapsed_ms"],
        )

        # 维护短期记忆：用户消息 + 助手回答。超过上限时把最早的一批压缩成摘要。
        state.chat_history.append(ChatTurn(role="user", content=message))
        state.chat_history.append(ChatTurn(role="assistant", content=reply))
        if len(state.chat_history) > max_turns * 2:
            overflow = state.chat_history[: -max_turns * 2]
            remaining = state.chat_history[-max_turns * 2 :]
            summary = await summarize_history(self._llm, overflow)
            if summary:
                if state.history_summary:
                    state.history_summary = (
                        f"{state.history_summary}\n{summary}".strip()
                    )
                else:
                    state.history_summary = summary
            state.chat_history = remaining
        await self._repository.save(session_id, state)

        # 从本轮对话抽取长期记忆事实（拥有物 / 偏好）
        for fact in extract_owned_facts(message):
            await self._long_term_memory.add(user_key, fact)
        for fact in extract_preference_facts(message):
            await self._long_term_memory.add(user_key, fact)

        return build_response(
            messages=[reply],
            actions=[],
            state=state,
        )

    def _format_fact(self, fact: MemoryFact) -> str:
        if fact.category == "owned_pal":
            return f"用户拥有帕鲁：{fact.content}"
        if fact.category == "preference":
            return f"用户偏好：{fact.content}"
        return fact.content

    async def _record_trace(
        self,
        *,
        session_id: str,
        user_key: str,
        user_message: str,
        reply: str,
        result: AgentLoopResult | None,
        latency_ms: int,
    ) -> None:
        if self._trace_store is None:
            return
        tool_calls = list(result.tool_calls) if result else []
        used_tools = bool(tool_calls)
        had_error = bool(result and result.error) or (result is None)
        total = len(tool_calls)
        ok = sum(1 for tc in tool_calls if tc.success)
        trace = AgentTrace(
            session_id=session_id,
            user_key=user_key,
            user_message=user_message,
            reply=reply,
            model=result.model if result else "",
            llm_rounds=list(result.llm_rounds) if result else [],
            error=result.error if result else ("workflow 异常" if result is None else ""),
            latency_ms=latency_ms,
            used_tools=used_tools,
            had_error=had_error,
            tool_success_rate=(ok / total) if total else 1.0,
            reply_length=len(reply),
        )
        try:
            await self._trace_store.record(trace)
        except Exception:  # noqa: BLE001 — 监测失败不阻塞主流程
            pass

    async def _handle_expand_pal(
        self, session_id: str, state: SessionState, pal_name: str
    ) -> dict:
        pal = await self._client.resolve_pal(pal_name)
        pal_id = pal.get("id") or pal_name
        pal_cn = pal.get("cn_name") or pal_name
        state.target_pal = pal_id
        state.confirmed_target_pal = pal_id
        await self._repository.save(session_id, state)
        messages, actions = await query_parents_and_record(
            session_id=session_id,
            state=state,
            repository=self._repository,
            client=self._client,
            pal_id=pal_id,
        )
        messages.insert(0, f"目标：{pal_cn}，正在查询父母。")
        state = await self._repository.get(session_id) or state
        return build_response(messages=messages, actions=actions, state=state)

    async def _handle_pal_stats(self, session_id: str, state: SessionState) -> dict:
        try:
            data = await self._client.query_stats()
        except Exception:
            data = {}
        total = data.get("total_pals")
        if total is None:
            return build_response(
                messages=["暂无法获取帕鲁统计信息。"],
                actions=[],
                state=state,
            )
        return build_response(
            messages=[f"目前数据库中共有 {total} 只帕鲁。"],
            actions=[],
            state=state,
        )

    def _general_reply(self, message: str, reason: str) -> str:
        return (
            "我是帕鲁配种助手。你可以这样问我：\n"
            "· 手工最高的是哪只帕鲁\n"
            "· 烧火最高的是哪只帕鲁\n"
            "· 墨罗娜怎么配种\n"
            "· 一共有多少帕鲁\n"
            f"（本条未命中业务意图：{reason}）"
        )

    async def handle_action(self, data: ActionInput) -> dict:
        state = await self._load_or_create_state(data.session_id)

        if data.action == ACTION_CONFIRM_TARGET:
            if not data.pal_id:
                raise ValueError("pal_id is required")
            state.target_pal = data.pal_id
            state.confirmed_target_pal = data.pal_id
            await self._repository.save(data.session_id, state)
            messages, actions = await query_parents_and_record(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                pal_id=data.pal_id,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if data.action == ACTION_EXPAND_PARENT:
            if not data.pal_id:
                raise ValueError("pal_id is required")
            if not state.target_pal:
                raise StateConflictError("请先确认目标帕鲁再展开")

            duplicate_count = self._repository.get_expand_count(
                data.session_id, data.pal_id
            )
            current_depth = state.node_depths.get(data.pal_id, 0)
            ensure_expand_allowed(
                state,
                duplicate_count=duplicate_count,
                duplicate_limit=self._settings.duplicate_expand_limit,
                current_depth=current_depth,
            )

            if data.pal_id in state.explored_nodes:
                return build_response(
                    messages=build_reused_node_response(data.pal_id),
                    actions=[],
                    state=state,
                )

            await self._repository.append_click(
                data.session_id,
                ClickEvent(pal_id=data.pal_id),
            )
            messages, actions = await query_parents_and_record(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                pal_id=data.pal_id,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if data.action == ACTION_SELECT_PARENT_PAIR:
            if not data.child_pal_id:
                raise ValueError("child_pal_id is required")
            if data.pair_index is None:
                raise ValueError("pair_index is required")
            messages, actions = await select_parent_pair(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                child_pal_id=data.child_pal_id,
                pair_index=data.pair_index,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        if data.action == ACTION_CONTINUE_FROM_PARENT:
            if not data.pal_id:
                raise ValueError("pal_id is required")
            if not state.target_pal:
                raise StateConflictError("请先确认目标帕鲁再继续追溯")

            duplicate_count = self._repository.get_expand_count(
                data.session_id, data.pal_id
            )
            current_depth = state.node_depths.get(data.pal_id, 0)
            ensure_expand_allowed(
                state,
                duplicate_count=duplicate_count,
                duplicate_limit=self._settings.duplicate_expand_limit,
                current_depth=current_depth,
            )

            await self._repository.append_click(
                data.session_id,
                ClickEvent(pal_id=data.pal_id),
            )
            messages, actions = await query_parents_and_record(
                session_id=data.session_id,
                state=state,
                repository=self._repository,
                client=self._client,
                pal_id=data.pal_id,
            )
            state = await self._repository.get(data.session_id) or state
            return build_response(messages=messages, actions=actions, state=state)

        raise ValueError(f"unsupported action: {data.action}")
