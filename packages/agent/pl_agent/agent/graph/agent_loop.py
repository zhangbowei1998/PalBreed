"""LLM agent loop — chat with function-calling tools until final answer.

使用 OpenAI wire-format 消息（dict）与模型交互，以便完整透传
assistant 的 ``tool_calls`` 帧和 ``tool`` 结果帧。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..llm import LLMClient
from ..monitoring.models import LlmRoundRecord, ToolCallRecord
from ..tools import ToolError, ToolRegistry


class AgentLoopError(Exception):
    pass


@dataclass
class AgentLoopResult:
    """AgentLoop.run 的结构化结果（供监测/上层使用）。"""

    content: str
    model: str = ""
    llm_rounds: list[LlmRoundRecord] = field(default_factory=list)
    error: str = ""

    @property
    def tool_calls(self) -> list[ToolCallRecord]:
        return [tc for r in self.llm_rounds for tc in r.tool_calls]


def _tool_message(tool_call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


class AgentLoop:
    def __init__(
        self,
        *,
        llm: LLMClient,
        registry: ToolRegistry,
        system_prompt: str,
        max_rounds: int = 5,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._system_prompt = system_prompt
        self._max_rounds = max_rounds

    async def run(
        self,
        user_message: str,
        history: list[dict] | None = None,
        long_term_facts: list[str] | None = None,
        history_summary: str | None = None,
    ) -> AgentLoopResult:
        """Run one user turn with two memory layers + optional compressed context.

        - ``history``: short-term memory — prior user/assistant turns.
        - ``long_term_facts``: long-term memory — persistent user facts
          (e.g. owned pals) injected into the system prompt.
        - ``history_summary``: compressed summary of earlier turns that were
          dropped from ``history``, injected into the system prompt.
        """
        tools = self._registry.to_openai_functions()
        system_content = self._system_prompt
        if long_term_facts:
            facts_block = "\n".join(f"- {fact}" for fact in long_term_facts)
            system_content += (
                "\n\n【长期记忆 - 关于该用户的已知事实】\n"
                f"{facts_block}\n"
                "（在回答时自然运用这些事实，例如优先推荐用户已拥有的帕鲁。）"
            )
        if history_summary:
            system_content += (
                "\n\n【上下文记忆 - 本会话更早对话的摘要】\n"
                f"{history_summary}\n"
                "（这段是较早对话的压缩摘要，请在回答时结合上下文理解用户意图。）"
            )
        messages: list[dict] = [
            {"role": "system", "content": system_content},
            *(history or []),
            {"role": "user", "content": user_message},
        ]

        rounds: list[LlmRoundRecord] = []
        last_model = ""
        error = ""

        for i in range(self._max_rounds):
            try:
                response = await self._llm.chat(messages, tools=tools)
                last_model = response.model or last_model
            except Exception as exc:  # noqa: BLE001
                error = f"LLM 调用失败: {exc}"
                rounds.append(LlmRoundRecord(round=i + 1, requested_tools=False))
                return AgentLoopResult(
                    content="", model=last_model, llm_rounds=rounds, error=error
                )

            round_rec = LlmRoundRecord(
                round=i + 1, requested_tools=bool(response.tool_calls)
            )

            if not response.tool_calls:
                rounds.append(round_rec)
                return AgentLoopResult(
                    content=response.content,
                    model=last_model,
                    llm_rounds=rounds,
                    error=error,
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
            )
            for tool_call in response.tool_calls:
                record = ToolCallRecord(
                    name=tool_call.name, arguments=tool_call.arguments
                )
                try:
                    executed = await self._registry.execute(
                        tool_call.name, tool_call.arguments
                    )
                    record.result = executed["result"]
                    record.success = True
                    content = json.dumps(executed["result"], ensure_ascii=False)
                except ToolError as exc:
                    record.success = False
                    record.error = str(exc)
                    content = json.dumps({"error": str(exc)}, ensure_ascii=False)
                round_rec.tool_calls.append(record)
                messages.append(_tool_message(tool_call.id, content))
            rounds.append(round_rec)

        return AgentLoopResult(
            content="已达到最大工具调用轮次，无法生成回答。",
            model=last_model,
            llm_rounds=rounds,
            error=error,
        )
