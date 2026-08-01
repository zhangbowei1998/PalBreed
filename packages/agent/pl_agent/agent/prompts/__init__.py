"""System prompts — 集中管理所有 LLM 提示词（单独 .md 文件，便于阅读与优化）。

每个 .md 文件对应一个提示词：
- assistant.md          主配种助手（AgentLoop 系统提示词）
- intent_recognizer.md  意图识别器
- context_compress.md   对话历史压缩（含 {history} 占位符）

通过 importlib.resources 读取，源码模式与安装（wheel）模式均可用。
"""

from __future__ import annotations

from importlib import resources

__all__ = [
    "ASSISTANT_SYSTEM_PROMPT",
    "INTENT_RECOGNIZER_SYSTEM_PROMPT",
    "CONTEXT_COMPRESS_PROMPT",
]


def _load(name: str) -> str:
    return (
        resources.files(__package__).joinpath(name).read_text(encoding="utf-8").strip()
    )


ASSISTANT_SYSTEM_PROMPT: str = _load("assistant.md")
INTENT_RECOGNIZER_SYSTEM_PROMPT: str = _load("intent_recognizer.md")
CONTEXT_COMPRESS_PROMPT: str = _load("context_compress.md")
