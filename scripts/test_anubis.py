"""Test breeding path for Anubis (handiwork=6, not wild)."""

import json, urllib.request

BASE = "http://localhost:8000"


def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req).read())


# Anubis query
r = post("/api/query", {"input": "阿努比斯"})
d = r["data"]
pal = d["pal"]
tree = d["breeding_tree"]
print(f"🎯 Target: {pal['cn_name']} (#{pal['number']})")
print(f"   CombiRank: {pal['combi_rank']}")
print(f"   Work: {pal['work_suitability']}")
print(f"   is_wild: {pal['is_wild']}")
print()
print(f"📋 Breeding Tree: {tree['total_paths']} paths, max_depth={tree['max_depth']}")

if tree["best_path"]:
    bp = tree["best_path"]
    print(f"   Best path: {bp['total_steps']} steps")
    print(f"   Leaf pals (wild): {[l['cn_name'] for l in bp['leaf_pals']]}")
    for s in bp["steps"]:
        print(
            f"   🥚 {s['parent_a']['cn_name']} + {s['parent_b']['cn_name']} = {s['child']['cn_name']}"
        )
    if bp.get("display_text"):
        for line in bp["display_text"].split("\n"):
            print(f"      {line}")
else:
    print(f"   No breeding path available")
    print(f"   Message: {tree.get('message', 'N/A')}")

print()

# Also test a low-level handiwork query
r = post("/api/query", {"input": "手工:6"})
d = r["data"]
print(f"🔍 手工:6 → {d['total']} candidates:")
for c in d["candidates"][:5]:
    p = c["pal"]
    print(
        f"   {p['cn_name']}: handiwork={c['all_suitabilities'].get('handiwork','?')}, wild={p['is_wild']}"
    )
