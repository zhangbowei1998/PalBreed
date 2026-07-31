"""Test breeding path for highest handiwork pal via API."""

import json, urllib.request

BASE = "http://localhost:8000"


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body, headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(f"{BASE}{path}").read())


# 1. Query handiwork:10 (out of range)
r = post("/api/query", {"input": "手工:10"})
d = r["data"]
print(f"1. 手工:10 → {d['result_type']}, max_available=Lv{d['max_available']}")
print(f"   {d['message']}\n")

# 2. Query handiwork:8 (get top candidates)
r = post("/api/query", {"input": "手工:8"})
d = r["data"]
print(f"2. 手工:8 → {d['total']} candidates")
for c in d["candidates"]:
    p = c["pal"]
    ws = c["all_suitabilities"]
    print(
        f"   {p['cn_name']} #{p['number']}: handiwork={ws['handiwork']}, rank={p['combi_rank']}, wild={p['is_wild']}"
    )
top_pal = d["candidates"][0]["pal"]
print()

# 3. Get breeding tree for top pal
r = get(f"/api/breeding/tree/{top_pal['id']}")
d = r["data"]
tree = d["breeding_tree"]
print(
    f"3. {d['pal']['cn_name']} 配种树: {tree['total_paths']} paths, max_depth={tree['max_depth']}"
)
if tree["best_path"]:
    bp = tree["best_path"]
    print(f"   Steps: {bp['total_steps']}")
    print(f"   Leaves: {[l['cn_name'] for l in bp['leaf_pals']]}")
    for s in bp["steps"]:
        print(
            f"   {s['parent_a']['cn_name']} + {s['parent_b']['cn_name']} = {s['child']['cn_name']}"
        )
    if bp.get("display_text"):
        for line in bp["display_text"].split("\n"):
            print(f"   {line}")
elif tree["total_paths"] == 0:
    print(f"   No breeding path: {tree.get('message', 'N/A')}")
