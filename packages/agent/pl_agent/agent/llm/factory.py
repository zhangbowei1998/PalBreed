"""LLM client factory — create provider instances from config.

新增模型接入方式：在 :data:`_REGISTRY` 注册一个 provider 名称 + 构造器即可，
业务代码通过 :func:`create_llm_client` 拿到统一的 ``LLMClient``。
"""

from __future__ import annotations

from typing import Callable

from .base import LLMClient, LLMConfig, LLMError
from .deepseek import DeepSeekClient

_REGISTRY: dict[str, Callable[[LLMConfig], LLMClient]] = {
    "deepseek": DeepSeekClient,
    # OpenAI 兼容服务可在此注册，例如：
    # "openai": OpenAIClient,
    # "ollama": OllamaClient,
}


def register_provider(name: str, builder: Callable[[LLMConfig], LLMClient]) -> None:
    """Register a new provider adapter at runtime."""
    _REGISTRY[name.lower()] = builder


def create_llm_client(config: LLMConfig) -> LLMClient:
    """Create the LLM client matching ``config.provider``."""
    provider = (config.provider or "").strip().lower()
    builder = _REGISTRY.get(provider)
    if builder is None:
        raise LLMError(
            f"unsupported LLM provider '{provider}'; " f"available: {sorted(_REGISTRY)}"
        )
    return builder(config)
