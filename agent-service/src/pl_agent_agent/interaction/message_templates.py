"""Message template helpers."""

from __future__ import annotations


def top_candidates_message(lines: list[str]) -> str:
    title = "检测到手工最高候选，请确认目标："
    return "\n".join([title, *lines])


def parent_pairs_message(target: str, pairs: list[dict]) -> str:
    if not pairs:
        return f"{target} 当前无可用父母组合，已标记为叶子节点。"
    lines = [f"{target} 的父母候选："]
    for item in pairs:
        lines.append(
            f"- {item.get('parent_a')} + {item.get('parent_b')} ({item.get('method', 'breed')})"
        )
    return "\n".join(lines)


def repeated_node_message(pal_id: str) -> str:
    return f"{pal_id} 已查询过，已复用历史结果。"


def guard_block_message(reason: str) -> str:
    return f"无法继续展开：{reason}"


def route_message(text_tree: str, partial: bool) -> str:
    if partial:
        return f"路线生成超时，返回部分结果：\n{text_tree}"
    return f"已生成配种路线：\n{text_tree}"
