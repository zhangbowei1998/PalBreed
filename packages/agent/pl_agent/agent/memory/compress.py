"""Context compression — summarize old turns to keep the window bounded.

短期记忆不可能无限增长：当会话历史超过阈值时，把最早的一批对话用 LLM
压缩成一段中文摘要（上下文记忆），只保留最近的原始轮次。摘要会在后续
每一轮注入 system prompt，让模型仍然"记得"更早的对话。
"""

from __future__ import annotations

from ..llm import LLMClient
from ..state.models import ChatTurn

_COMPRESS_PROMPT = """\
下面是一段幻兽帕鲁配种助手的对话历史。请把它压缩成一段简洁的中文摘要，要求：
1. 保留用户已经问过的帕鲁名字、已经确定的配种目标、已经得到的配种方案（父代组合）。
2. 保留用户提到过的自己拥有的帕鲁、偏好、昵称等个人信息。
3. 不要写"用户问/助手答"这类过程性描述，直接提炼事实。
4. 如果后面没有值得保留的信息，返回"（无重要信息）"。

对话历史：
{history}
"""


async def summarize_history(llm: LLMClient, turns: list[ChatTurn]) -> str:
    """用 LLM 把一段对话历史压缩成摘要。

    传入的 ``turns`` 必须是已按时间排序的 ``ChatTurn`` 列表。
    """
    if not turns:
        return ""
    lines = [f"{turn.role}: {turn.content}" for turn in turns]
    history_block = "\n".join(lines)
    prompt = _COMPRESS_PROMPT.format(history=history_block)

    try:
        response = await llm.chat([{"role": "user", "content": prompt}])
        summary = response.content.strip()
    except Exception:  # noqa: BLE001 — 压缩失败不阻塞主流程
        return ""
    if not summary:
        return ""
    return summary
