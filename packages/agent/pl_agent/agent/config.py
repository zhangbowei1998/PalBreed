"""Runtime configuration for pl_agent.agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the package root (repo/packages/agent/.env).
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PACKAGE_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    breeding_api_base_url: str = "http://localhost:8000"
    max_depth: int = 10
    max_nodes: int = 200
    route_timeout_ms: int = 8000
    top_candidates: int = 3
    duplicate_expand_limit: int = 3
    # LLM
    llm_provider: str = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_timeout_s: float = 15.0
    llm_enabled: bool = False
    # Memory
    default_user_key: str = "default"
    short_term_max_turns: int = 12  # 短期记忆保留最近 N 轮（含 user+assistant）
    long_term_store: str = "file"  # "file" | "postgres"
    database_url: str = "postgresql://postgres@localhost:5432/pl_agent"
    # Auth / user system
    user_store: str = "file"  # "file" | "postgres"
    auth_secret: str = "dev-secret-change-me"
    auth_token_ttl_s: int = 7 * 24 * 3600


_WORK_TYPE_CN = {
    "handiwork": "手工",
    "kindling": "生火",
    "watering": "浇水",
    "planting": "播种",
    "generating_electricity": "发电",
    "gathering": "采集",
    "lumbering": "伐木",
    "mining": "采矿",
    "cooling": "冷却",
    "medicine": "制药",
    "transporting": "搬运",
    "farming": "牧场",
}

_CN_TO_EN_WORK_TYPE = {
    "手工": "handiwork",
    "手工作业": "handiwork",
    "制作": "handiwork",
    "生火": "kindling",
    "烧火": "kindling",
    "点火": "kindling",
    "火焰": "kindling",
    "浇水": "watering",
    "灌溉": "watering",
    "播种": "planting",
    "种植": "planting",
    "种地": "planting",
    "发电": "generating_electricity",
    "电力": "generating_electricity",
    "充电": "generating_electricity",
    "采集": "gathering",
    "收获": "gathering",
    "伐木": "lumbering",
    "砍树": "lumbering",
    "采矿": "mining",
    "挖矿": "mining",
    "冷却": "cooling",
    "降温": "cooling",
    "制冷": "cooling",
    "制药": "medicine",
    "医药": "medicine",
    "搬运": "transporting",
    "运输": "transporting",
    "牧场": "farming",
    "放牧": "farming",
}


def work_type_to_cn(work_type: str) -> str:
    return _WORK_TYPE_CN.get(work_type, work_type)


def resolve_work_type_keyword(text: str) -> str | None:
    """从中文文本里提取工种关键词，返回内部字段名；找不到返回 None."""
    for keyword, work_type in _CN_TO_EN_WORK_TYPE.items():
        if keyword in text:
            return work_type
    return None


def load_settings() -> Settings:
    return Settings(
        breeding_api_base_url=os.getenv(
            "BREEDING_API_BASE_URL", "http://localhost:8000"
        ),
        max_depth=int(os.getenv("AGENT_MAX_DEPTH", "10")),
        max_nodes=int(os.getenv("AGENT_MAX_NODES", "200")),
        route_timeout_ms=int(os.getenv("AGENT_ROUTE_TIMEOUT_MS", "8000")),
        top_candidates=int(os.getenv("AGENT_TOP_CANDIDATES", "3")),
        duplicate_expand_limit=int(os.getenv("AGENT_DUPLICATE_EXPAND_LIMIT", "3")),
        llm_provider=os.getenv("LLM_PROVIDER", "deepseek"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "15")),
        llm_enabled=os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes"},
        default_user_key=os.getenv("DEFAULT_USER_KEY", "default"),
        short_term_max_turns=int(os.getenv("SHORT_TERM_MAX_TURNS", "12")),
        long_term_store=os.getenv("LONG_TERM_STORE", "file"),
        database_url=os.getenv(
            "DATABASE_URL", "postgresql://postgres@localhost:5432/pl_agent"
        ),
        user_store=os.getenv("USER_STORE", "file"),
        auth_secret=os.getenv("AUTH_SECRET", "dev-secret-change-me"),
        auth_token_ttl_s=int(os.getenv("AUTH_TOKEN_TTL_S", str(7 * 24 * 3600))),
    )
