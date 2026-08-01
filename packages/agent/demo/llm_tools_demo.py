"""Demo: LLM full-conversation + deterministic tools (function calling).

Run:
    cd packages/agent && PYTHONPATH=pl_agent uv run python demo/llm_tools_demo.py
"""

from __future__ import annotations

import asyncio

from pl_agent.agent.clients.breeding_api_client import BreedingApiClient
from pl_agent.agent.config import load_settings
from pl_agent.agent.graph.agent_loop import AgentLoop
from pl_agent.agent.llm import LLMConfig, create_llm_client
from pl_agent.agent.prompts import ASSISTANT_SYSTEM_PROMPT
from pl_agent.agent.tools import ToolRegistry, build_breeding_tools


async def run_once(question: str) -> str:
    settings = load_settings()
    llm = create_llm_client(
        LLMConfig(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    )
    api = BreedingApiClient(base_url=settings.breeding_api_base_url)
    registry = ToolRegistry(
        build_breeding_tools(api, top_n_default=settings.top_candidates)
    )
    loop = AgentLoop(llm=llm, registry=registry, system_prompt=ASSISTANT_SYSTEM_PROMPT)
    return await loop.run(question)


async def main() -> None:
    questions = [
        "墨罗娜怎么配种",
        "烧火最高的是哪只帕鲁",
        "一共有多少帕鲁",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        try:
            answer = await run_once(question)
            print(f"A: {answer}\n{'=' * 60}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
