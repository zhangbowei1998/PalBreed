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
from ..interaction.presenter import build_data_cards, build_response
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
from ..prompts import ASSISTANT_SYSTEM_PROMPT
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

_BREEDING_KEYWORDS = (
    "怎么配种",
    "怎么配",
    "怎样配",
    "如何配",
    "怎么生",
    "怎么合成",
    "配种组合",
    "配种方案",
    "配种",
    "的父母",
)


def extract_breeding_target(message: str) -> str | None:
    """从「XX怎么配种 / XX的父母」类消息提取帕鲁名候选（需 resolve 验证）。

    返回配种关键词之前的主体文本；关键词缺失或在开头时返回 None。
    """
    text = message.strip()
    if not text:
        return None
    for kw in _BREEDING_KEYWORDS:
        idx = text.find(kw)
        if idx > 0:
            candidate = text[:idx].strip(" ，,。！!？?：:、")
            if candidate:
                return candidate
    return None


def _compact_stats(stats: dict) -> str:
    """把 stats 字典压缩成可读的一行，如 'HP 95 / 攻击 80 / 防御 70'。"""
    if not stats:
        return ""
    order = ["hp", "attack", "defense", "magic", "magic_defense", "stamina"]
    parts = []
    for key in order:
        if key in stats and stats[key] is not None:
            parts.append(f"{key.title()} {stats[key]}")
    for key, value in stats.items():
        if value is not None and key not in order:
            parts.append(f"{key} {value}")
    return " / ".join(parts[:6])


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
                system_prompt=ASSISTANT_SYSTEM_PROMPT,
            )

    def _user_key(self, session_id: str, user_id: str | None = None) -> str:
        # 有登录用户时按用户隔离长期记忆；匿名会话退回 default。
        return user_id or self._settings.default_user_key

    def _session_key(self, session_id: str, user_id: str | None = None) -> str:
        """短期记忆存储 key：按用户隔离，避免不同用户会话串扰。

        登录用户: u:{user_id}:{session_id}
        匿名用户: u:default:{session_id}
        """
        user = user_id or self._settings.default_user_key
        return f"u:{user}:{session_id}"

    async def _load_or_create_state(self, session_id: str) -> SessionState:
        state = await self._repository.get(session_id)
        if state:
            return state
        state = SessionState(session_id=session_id)
        state.limits.max_depth = self._settings.max_depth
        state.limits.max_nodes = self._settings.max_nodes
        return await self._repository.save(session_id, state)

    async def handle_chat(self, data: ChatInput, *, text_callback=None) -> dict:
        # 短期记忆按用户隔离：session_id 与 user 绑定成存储 key（匿名也加 default 前缀）
        data.session_id = self._session_key(data.session_id, data.user_id)
        state = await self._load_or_create_state(data.session_id)

        if self._agent_loop is not None:
            return await self._handle_llm_chat(
                data.session_id, state, data.message, user_id=data.user_id,
                text_callback=text_callback,
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

        if intent.intent == Intent.PAL_DETAIL and intent.pal_name:
            return await self._handle_pal_detail(data.session_id, intent.pal_name, state)

        if intent.intent == Intent.ITEM_QUERY:
            return await self._handle_item_query(data.session_id, intent.item_name, data.message, state)

        if intent.intent == Intent.PASSIVE_QUERY and intent.passive_name:
            return await self._handle_passive_query(
                data.session_id, intent.passive_name, state
            )

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
        *,
        text_callback=None,
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
                    text_callback=text_callback,
                )
                reply = result.content
            except Exception as exc:  # noqa: BLE001
                reply = f"LLM 处理失败：{exc}"
                result = None

        # 监测：组装本次对话 trace 并记录
        trace_info = await self._record_trace(
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

        meta: dict = {}
        if trace_info:
            meta["trace"] = trace_info

        # 若 LLM 调用了 query_parent_pairs 且成功，则复用确定性配种链路，
        # 生成「父母候选」消息 + select_parent_pair 操作，让前端可点击并渲染配种二叉树。
        extra_messages: list[str] = []
        extra_actions: list[dict] = []
        used_breeding_tool = False
        if result is not None:
            for tc in result.tool_calls:
                if tc.name == "query_parent_pairs" and tc.success:
                    used_breeding_tool = True
                    pal = (tc.result or {}).get("pal") or {}
                    pal_id = pal.get("id") or ""
                    if pal_id:
                        # LLM 查询某帕鲁配种方案 = 用户对该帕鲁感兴趣，
                        # 把它设为当前目标，后续追溯 / 展开才能正常进行。
                        if not state.target_pal:
                            state.target_pal = pal_id
                            state.confirmed_target_pal = pal_id
                        try:
                            pm, pa = await query_parents_and_record(
                                session_id=session_id,
                                state=state,
                                repository=self._repository,
                                client=self._client,
                                pal_id=pal_id,
                            )
                            extra_messages.extend(pm)
                            extra_actions.extend(pa)
                        except Exception:  # noqa: BLE001
                            # 配种链路异常不影响 LLM 文本回复
                            pass
            if extra_messages:
                state = await self._repository.get(session_id) or state

        # 兜底：LLM 未调用配种工具时，若消息明显是「XX怎么配种 / XX的父母」类
        # 意图，按规则提取帕鲁名并复用确定性配种链路，生成可点击的父母候选，
        # 避免 LLM 直接文本回答（不调用工具）导致前端无法继续选择。
        if not used_breeding_tool:
            target = extract_breeding_target(message)
            if target:
                try:
                    pal = await self._client.resolve_pal_name(target)
                except Exception:  # noqa: BLE001
                    pal = None
                if pal and pal.get("id"):
                    pal_id = pal["id"]
                    # 配种目标 = 用户感兴趣的帕鲁，设为当前目标供追溯 / 展开使用。
                    if not state.target_pal:
                        state.target_pal = pal_id
                        state.confirmed_target_pal = pal_id
                    try:
                        pm, pa = await query_parents_and_record(
                            session_id=session_id,
                            state=state,
                            repository=self._repository,
                            client=self._client,
                            pal_id=pal_id,
                        )
                        extra_messages.extend(pm)
                        extra_actions.extend(pa)
                        used_breeding_tool = True
                    except Exception:  # noqa: BLE001
                        # 配种链路异常不影响 LLM 文本回复
                        pass
                if extra_messages:
                    state = await self._repository.get(session_id) or state

        # 话题切换清理：本轮未调用配种工具（用户问的是与配种无关的新问题，
        # 例如「石头怎么获取」），应清空上一轮残留的配种树 / 目标，
        # 避免页面继续展示无关的配种路线。
        if not used_breeding_tool and (state.selected_pairs or state.target_pal):
            state.selected_pairs = []
            state.target_pal = None
            state.confirmed_target_pal = None
            state.current_focus_pal = None
            state.edges = []
            state.candidate_pairs = {}
            state.pending_frontier = []
            state.explored_nodes = []
            state.node_depths = {}
            state.click_trace = []
            state.touch()
            await self._repository.save(session_id, state)

        resp = build_response(
            messages=[reply, *extra_messages],
            actions=extra_actions,
            state=state,
            meta=meta,
        )
        # 结构化数据卡片（被动/掉落/配方/技能/详情）— 前端据此渲染
        data_cards = build_data_cards(result.tool_calls if result is not None else None)
        if data_cards:
            resp["data_cards"] = data_cards
        return resp

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
    ) -> dict | None:
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
        # 返回给前端的工具调用摘要（不依赖 trace_store 是否启用）
        trace_info = {
            "latency_ms": latency_ms,
            "model": trace.model,
            "used_tools": used_tools,
            "had_error": had_error,
            "tool_success_rate": trace.tool_success_rate,
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "success": tc.success,
                    "error": tc.error,
                    "result": tc.result,
                }
                for tc in tool_calls
            ],
        }
        if self._trace_store is None:
            return trace_info
        try:
            await self._trace_store.record(trace)
        except Exception:  # noqa: BLE001 — 监测失败不阻塞主流程
            pass
        return trace_info

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

    async def _handle_pal_detail(
        self, session_id: str, pal_name: str, state: SessionState
    ) -> dict:
        """Fallback：帕鲁详情（属性/技能/掉落/伙伴技能）。"""
        try:
            pal = await self._client.resolve_pal(pal_name)
            if not pal or not pal.get("id"):
                return build_response(
                    messages=[f"未找到帕鲁：{pal_name}"], actions=[], state=state
                )
            pal_id = pal.get("id")
            pal_cn = pal.get("cn_name") or pal_name
            detail = await self._client.get_pal_detail_full(pal_id)
            skills = detail.get("skills") or []
            drops = detail.get("drops") or []
            stats = detail.get("stats") or {}
            summary = [
                f"【{pal_cn} 详情】",
                f"- 可学技能：{len(skills)} 个",
                f"- 击杀掉落：{len(drops)} 种",
            ]
            if stats:
                summary.append(f"- 基础属性：{_compact_stats(stats)}")
            return build_response(messages=["\n".join(summary)], actions=[], state=state)
        except Exception as exc:  # noqa: BLE001
            return build_response(
                messages=[f"查询 {pal_name} 详情失败：{exc}"], actions=[], state=state
            )

    async def _handle_item_query(
        self, session_id: str, item_name: str | None, raw: str, state: SessionState
    ) -> dict:
        """Fallback：物品掉落来源 / 制作配方。"""
        name = (item_name or raw or "").strip()
        if not name:
            return build_response(
                messages=["请告诉我你想查哪个物品/材料。"], actions=[], state=state
            )
        try:
            # 制作类关键词 → 配方；否则优先掉落来源
            if any(k in raw for k in ("怎么做", "制作", "配方", "合成")):
                recipe = await self._client.get_item_recipe(name)
                if recipe:
                    first = recipe[0]
                    station = first.get("station") or first.get("facility") or ""
                    mats = first.get("materials") or []
                    mat_str = "、".join(
                        f"{m.get('name', m.get('item_name', ''))}×{m.get('count', m.get('quantity', ''))}"
                        for m in mats[:6]
                    )
                    lines = [f"【{name} 制作配方】"]
                    if station:
                        lines.append(f"- 设施：{station}")
                    if mat_str:
                        lines.append(f"- 材料：{mat_str}")
                    return build_response(
                        messages=["\n".join(lines)], actions=[], state=state
                    )
                return build_response(
                    messages=[f"未找到 {name} 的制作配方。"], actions=[], state=state
                )
            # 掉落来源
            pals = await self._client.get_item_drops(name)
            if pals:
                top = pals[:5]
                names = "、".join(
                    p.get("cn_name", p.get("pal_name", str(p.get("pal_id", ""))))
                    for p in top
                )
                suffix = " 等" if len(pals) > 5 else ""
                return build_response(
                    messages=[f"【{name} 掉落来源】{names}{suffix}"],
                    actions=[],
                    state=state,
                )
            return build_response(
                messages=[f"未找到掉落 {name} 的帕鲁。"], actions=[], state=state
            )
        except Exception as exc:  # noqa: BLE001
            return build_response(
                messages=[f"查询 {name} 失败：{exc}"], actions=[], state=state
            )

    async def _handle_passive_query(
        self, session_id: str, passive_name: str, state: SessionState
    ) -> dict:
        """Fallback：按被动技能查拥有它的帕鲁。"""
        try:
            pals = await self._client.query_pals_by_passive(passive_name)
            if not pals:
                return build_response(
                    messages=[f"未找到拥有「{passive_name}」被动的帕鲁。"],
                    actions=[],
                    state=state,
                )
            top = pals[:8]
            names = "、".join(
                p.get("cn_name", p.get("pal_name", str(p.get("pal_id", ""))))
                for p in top
            )
            suffix = " 等" if len(pals) > 8 else ""
            return build_response(
                messages=[f"【{passive_name}】拥有该被动的帕鲁：{names}{suffix}"],
                actions=[],
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            return build_response(
                messages=[f"查询被动 {passive_name} 失败：{exc}"],
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
        # 短期记忆按用户隔离：session_id 与 user 绑定成存储 key（匿名也加 default 前缀）
        data.session_id = self._session_key(data.session_id, data.user_id)
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
                client=self._client,
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
