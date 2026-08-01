"""Intent and route helpers."""

from __future__ import annotations


def is_top_handiwork_query(message: str) -> bool:
    text = message.strip()
    return "手工" in text and ("最高" in text or "最强" in text)
