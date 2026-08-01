"""LLM provider adapters.

可插拔的 LLM 客户端适配层：业务代码只依赖 ``LLMClient`` 抽象，
通过 :func:`create_llm_client` 按配置创建具体实现（DeepSeek / OpenAI / 其他）。
"""

from __future__ import annotations

from .base import (
    ChatMessage,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMResponse,
    Role,
    ToolCall,
)
from .factory import create_llm_client

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMResponse",
    "Role",
    "ToolCall",
    "create_llm_client",
]
