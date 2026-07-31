"""Test: 墨罗娜 breeding tree (is_wild=True should still show paths)."""

import json, urllib.request

BASE = "http://localhost:8000"


def get(p):
    return json.loads(urllib.request.urlopen(f"{BASE}{p}").read())


r = get("/api/breeding/tree/MonochromeQueen?max_depth=5&all=true")
d = r["data"]
p = d["pal"]
t = d["breeding_tree"]

print(
    f"🎯 {p['cn_name']} (wild={p['is_wild']}, handiwork={p['work_suitability']['handiwork']}, rank={p['combi_rank']})"
)
print(f"   {t['total_paths']} paths, max_depth={t['max_depth']}")

# Check for the expected formula
for path in t["paths"]:
    for s in path["steps"]:
        parents = {s["parent_a"], s["parent_b"]}
        if "Renjishi" in str(parents) or "Celesdir_Noct" in str(parents):
            print(f"\n✅ 验证成功: {s['parent_a']} + {s['parent_b']} = {s['child']}")

# Show all paths
for i, path in enumerate(t["paths"][:10]):
    steps_str = " → ".join(
        f"{s['parent_a']}+{s['parent_b']}={s['child']}" for s in path["steps"]
    )
    print(f"   Path {i+1} ({path['total_steps']} steps): {steps_str}")

if len(t["paths"]) > 10:
    print(f"   ... +{len(t['paths'])-10} more paths")
