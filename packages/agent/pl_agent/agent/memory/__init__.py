"""Long-term memory — persistent user facts across sessions.

短期记忆 = 会话内 chat_history（workflow 维护）。
长期记忆 = 跨会话持久事实（例如"用户拥有阿努比斯"），按 user_key 维度存储。
"""

from __future__ import annotations

from .long_term import (
    LongTermMemory,
    LongTermMemoryStore,
    MemoryFact,
)
from .postgres import PostgresLongTermMemory

__all__ = [
    "LongTermMemory",
    "LongTermMemoryStore",
    "MemoryFact",
    "PostgresLongTermMemory",
]
