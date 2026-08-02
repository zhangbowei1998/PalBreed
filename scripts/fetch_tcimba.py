"""抓取 tc-imba 全量数据到 data/tc-imba/。

用法: python scripts/fetch_tcimba.py [output_dir]
默认输出: data/tc-imba/

抓取清单（核心 5 文件 + locales 本地化）:
- 根路径: version/pals/breeding/passives/items
- locales/zh-CN: pals/passives/skills/items/enums/partnerEffects/partnerTargets
- locales/en-US: pals

说明: skills/enums/partnerEffects/partnerTargets 只有本地化版本（根路径 404），
技能/枚举数据本体内嵌在 pals.json。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://data-palworld.tc-imba.com"

# (远端路径, 本地文件名)
FILES = [
    ("version.json", "version.json"),
    ("pals.json", "pals.json"),
    ("breeding.json", "breeding.json"),
    ("passives.json", "passives.json"),
    ("items.json", "items.json"),
    ("locales/zh-CN/pals.json", "pals_zh.json"),
    ("locales/en-US/pals.json", "pals_en.json"),
    ("locales/zh-CN/passives.json", "zh_passives.json"),
    ("locales/zh-CN/skills.json", "zh_skills.json"),
    ("locales/zh-CN/items.json", "zh_items.json"),
    ("locales/zh-CN/enums.json", "zh_enums.json"),
    ("locales/zh-CN/partnerEffects.json", "zh_partnerEffects.json"),
    ("locales/zh-CN/partnerTargets.json", "zh_partnerTargets.json"),
]


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pl-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/tc-imba")
    out.mkdir(parents=True, exist_ok=True)

    ok, failed = 0, []
    for remote, local in FILES:
        url = f"{BASE}/{remote}"
        try:
            data = fetch(url)
            # 校验返回的是 JSON（排除 404 HTML 页）
            json.loads(data.decode("utf-8"))
            (out / local).write_bytes(data)
            ok += 1
            print(f"✅ {local} ({len(data)} bytes)")
        except Exception as e:  # noqa: BLE001
            failed.append((remote, str(e)))
            print(f"❌ {remote}: {e}")
        time.sleep(0.2)

    print(f"\n成功 {ok}/{len(FILES)}")
    if failed:
        for remote, err in failed:
            print(f"  失败: {remote} -> {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
