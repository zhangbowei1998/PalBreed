"""Long-term memory implementation — file-backed persistent user facts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class MemoryFact:
    __slots__ = ("category", "content", "ts")

    def __init__(self, category: str, content: str, ts: str = "") -> None:
        self.category = category
        self.content = content
        self.ts = ts or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {"category": self.category, "content": self.content, "ts": self.ts}

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryFact":
        return cls(
            category=str(data.get("category", "general")),
            content=str(data.get("content", "")),
            ts=str(data.get("ts", "")),
        )


class LongTermMemoryStore(Protocol):
    async def load(self, user_key: str) -> list[MemoryFact]: ...

    async def add(self, user_key: str, fact: MemoryFact) -> None: ...

    async def reset(self, user_key: str) -> None: ...


class LongTermMemory:
    """File-backed long-term memory keyed by user.

    Facts are stored as JSON at ``data_dir / "long_term_memory.json"``.
    The store is intentionally simple; swap for Redis/DB later by implementing
    :class:`LongTermMemoryStore`.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir is None:
            # 包根 data 目录（packages/agent/data）
            data_dir = Path(__file__).resolve().parents[3] / "data"
        self._path = Path(data_dir) / "long_term_memory.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, list[MemoryFact]] = self._load_file()

    def _load_file(self) -> dict[str, list[MemoryFact]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        result: dict[str, list[MemoryFact]] = {}
        for user_key, facts in raw.items():
            result[str(user_key)] = [
                MemoryFact.from_dict(item) for item in facts if isinstance(item, dict)
            ]
        return result

    def _save_file(self) -> None:
        raw = {
            user_key: [fact.to_dict() for fact in facts]
            for user_key, facts in self._data.items()
        }
        self._path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def load(self, user_key: str) -> list[MemoryFact]:
        return list(self._data.get(user_key, []))

    async def add(self, user_key: str, fact: MemoryFact) -> None:
        if not fact.content.strip():
            return
        facts = self._data.setdefault(user_key, [])
        # 去重：同分类同内容不重复
        for existing in facts:
            if existing.category == fact.category and existing.content == fact.content:
                return
        facts.append(fact)
        self._save_file()

    async def reset(self, user_key: str) -> None:
        self._data.pop(user_key, None)
        self._save_file()


# ── 长期记忆抽取（规则式，把用户明示的偏好/拥有物转为事实） ──

_OWN_PATTERNS = [
    re.compile(
        r"我(?:有|已拥有|已经有|抓到了|培养了|抓了)\s*"
        r"[「『\"']?([\u4e00-\u9fffA-Za-z]+)[」』\"']?"
    ),
]

_PREFERENCE_PATTERNS = [
    re.compile(
        r"我(?:比较喜欢|喜欢|偏爱|常用|主要用|喜欢用)\s*"
        r"[「『\"']?([\u4e00-\u9fffA-Za-z]+)[」』\"']?"
    ),
]

_TRAILING_PARTICLES = frozenset("了啊呀吧呢吗嘛的啦哦噢哎喂唉哈哼呸哟")


def _clean_name(name: str) -> str:
    while name and name[-1] in _TRAILING_PARTICLES:
        name = name[:-1]
    return name.strip()


def extract_owned_facts(message: str) -> list[MemoryFact]:
    facts: list[MemoryFact] = []
    for pattern in _OWN_PATTERNS:
        for match in pattern.finditer(message):
            name = _clean_name(match.group(1))
            if name:
                facts.append(MemoryFact(category="owned_pal", content=name))
    return facts


def extract_preference_facts(message: str) -> list[MemoryFact]:
    facts: list[MemoryFact] = []
    for pattern in _PREFERENCE_PATTERNS:
        for match in pattern.finditer(message):
            name = _clean_name(match.group(1))
            if name:
                facts.append(MemoryFact(category="preference", content=name))
    return facts
