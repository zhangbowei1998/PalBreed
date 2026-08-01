"""Message template helpers."""

from __future__ import annotations


def top_candidates_message(lines: list[str]) -> str:
    title = "检测到手工最高候选，请确认目标："
    return "\n".join([title, *lines])


def parent_pairs_message(target: str, pairs: list[dict]) -> str:
    if not pairs:
        return f"{target} 当前无可用父母组合，已标记为叶子节点。"
    lines = [f"{target} 的父母候选："]
    for idx, item in enumerate(pairs, start=1):
        lines.append(
            f"{idx}. {item.get('parent_a')} + {item.get('parent_b')} ({item.get('method', 'breed')})"
        )
    lines.append("请选择一个父母组合继续。")
    return "\n".join(lines)


def repeated_node_message(pal_id: str) -> str:
    return f"{pal_id} 已查询过，已复用历史结果。"


def guard_block_message(reason: str) -> str:
    return f"无法继续展开：{reason}"


def selected_pair_message(
    child_name: str, parent_a_name: str, parent_b_name: str
) -> str:
    return (
        f"已选择 {child_name} 的父母组合：{parent_a_name} + {parent_b_name}。\n"
        "下一步请选择要继续追溯的父母。"
    )
