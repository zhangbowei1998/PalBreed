"""Re-parse cached HTML and save to PG (standalone for clean import)."""
import json, asyncio, sys
from pathlib import Path

sys.path.insert(0, "packages/core")
sys.path.insert(0, "packages/adapters")
sys.path.insert(0, "packages/api")
sys.path.insert(0, "packages")

from adapters.paldb.parser import PalDBParser
from adapters.paldb.adapter import PalDBAdapter
from adapters.postgres.adapter import PostgresWriter

adapter = PalDBAdapter()
parser = PalDBParser()
files = sorted(Path("data/raw/pages").glob("*.html"))
print(f"Re-parsing {len(files)} HTML files...")

pals = []
for i, f in enumerate(files):
    try:
        html = f.read_text(encoding="utf-8")
        r = parser.parse(html, f.stem)
        if r.get("cn_name") and r.get("combi_rank"):
            pals.append(adapter._dict_to_pal(r))
    except Exception:
        pass

# Dedup + merge work suitability
seen = {}
for p in pals:
    k = (p.cn_name, p.number)
    if k not in seen:
        seen[k] = p
    else:
        for fld in p.work_suitability.__dataclass_fields__:
            v = getattr(p.work_suitability, fld, 0)
            if v > getattr(seen[k].work_suitability, fld, 0):
                setattr(seen[k].work_suitability, fld, v)
unique = list(seen.values())

with_ws = sum(1 for p in unique if p.work_suitability.max_level() > 0)
print(f"Unique: {len(unique)}, with_work: {with_ws}")

# Show top 5 by handiwork
sorted_pals = sorted(unique, key=lambda p: p.work_suitability.handiwork, reverse=True)
for p in sorted_pals[:5]:
    ws = p.work_suitability.non_zero()
    print(f"  {p.cn_name}: handiwork={p.work_suitability.handiwork} work={ws}")

# Save JSON
data = {p.id: p.to_dict() for p in unique}
Path("data/processed/pal_data.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("JSON saved")

# Save PG
async def go():
    w = PostgresWriter()
    await w.connect()
    async with w._pool.acquire() as conn:
        await conn.execute("DELETE FROM pals")
    print("PG: old data deleted")
    await w.upsert_all(unique)
    c = await w.count()
    print(f"PG: {c} rows after upsert")
    await w.close()

asyncio.run(go())
