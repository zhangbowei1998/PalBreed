"""验证 API 所有端点."""

import json
import urllib.request

BASE = "http://localhost:8000"


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())


def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        BASE + path, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


# 1. Health
health = get("/health")
assert health["status"] == "ok", f"Health failed: {health}"
print("✅ Health:", health["pals_loaded"], "pals")

# 2. Name query
name = post("/api/query", {"input": "阿努比斯"})
assert name["data"]["type"] == "name_query", f"Name query failed: {name}"
assert name["data"]["pal"]["cn_name"] == "阿努比斯"
print(
    f"✅ Name query: {name['data']['pal']['cn_name']}, "
    f"paths={name['data']['breeding_tree']['total_paths']}"
)

# 3. Suitability
suit = post("/api/query", {"input": "手工:4"})
assert suit["data"]["type"] == "suitability_query"
print(f"✅ Suitability: {suit['data']['total']} candidates")

# 4. Out of range
oor = post("/api/query", {"input": "手工:6"})
assert oor["data"]["result_type"] == "out_of_range"
print(f"✅ Out of range: max={oor['data']['max_available']}")

# 5. Pal detail
pal = get("/api/pal/anubis")
assert pal["data"]["id"] == "anubis"
print(f"✅ Pal detail: {pal['data']['cn_name']} rank={pal['data']['combi_rank']}")

# 6. Breeding tree
tree = get("/api/breeding/tree/anubis")
assert "breeding_tree" in tree["data"]
print(f"✅ Breeding tree: paths={tree['data']['breeding_tree']['total_paths']}")

# 7. Stats
stats = get("/api/suitability/stats")
assert stats["data"]["total_pals"] >= 1
print(f"✅ Stats: {stats['data']['total_pals']} pals")

# 8. Not found
err = get("/api/breeding/tree/nonexistent")
assert not err["success"]
print(f"✅ Error: {err['error']['code']}")

print("\n🎉 All 8 API endpoints verified!")
