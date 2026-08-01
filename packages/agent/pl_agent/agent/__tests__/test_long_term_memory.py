from __future__ import annotations

import pytest

from pl_agent.agent.memory.long_term import (
    LongTermMemory,
    MemoryFact,
    extract_owned_facts,
    extract_preference_facts,
)


def test_extract_owned_facts(tmp_path):
    facts = extract_owned_facts("我已经有阿努比斯了")
    assert len(facts) == 1
    assert facts[0].category == "owned_pal"
    assert facts[0].content == "阿努比斯"


def test_extract_preference_facts(tmp_path):
    facts = extract_preference_facts("我比较喜欢墨罗娜")
    assert len(facts) == 1
    assert facts[0].category == "preference"
    assert facts[0].content == "墨罗娜"


@pytest.mark.asyncio
async def test_memory_add_and_load(tmp_path):
    memory = LongTermMemory(data_dir=tmp_path)
    await memory.add("u1", MemoryFact(category="owned_pal", content="阿努比斯"))
    await memory.add("u1", MemoryFact(category="owned_pal", content="阿努比斯"))  # 去重
    await memory.add("u1", MemoryFact(category="owned_pal", content="墨罗娜"))

    facts = await memory.load("u1")
    assert len(facts) == 2
    assert {f.content for f in facts} == {"阿努比斯", "墨罗娜"}


@pytest.mark.asyncio
async def test_memory_persists_across_instances(tmp_path):
    first = LongTermMemory(data_dir=tmp_path)
    await first.add("u1", MemoryFact(category="owned_pal", content="阿努比斯"))

    second = LongTermMemory(data_dir=tmp_path)
    facts = await second.load("u1")
    assert len(facts) == 1
    assert facts[0].content == "阿努比斯"


@pytest.mark.asyncio
async def test_memory_reset(tmp_path):
    memory = LongTermMemory(data_dir=tmp_path)
    await memory.add("u1", MemoryFact(category="owned_pal", content="阿努比斯"))
    await memory.reset("u1")
    assert await memory.load("u1") == []
