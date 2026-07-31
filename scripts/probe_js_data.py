"""Find pal data in paldb.cc JavaScript/JSON."""

import re
import json
import httpx

# Try the breed page - look for JS data
url = "https://paldb.cc/cn/Breed?child=Lamball"
resp = httpx.get(url, follow_redirects=True, timeout=20)
html = resp.text

# Search for JSON-like pal data in script tags or data attributes
# Common patterns: pal list, pal data, __NEXT_DATA__, etc.
patterns = [
    r"__NEXT_DATA__\s*=\s*({.*?});",
    r"window\.__DATA__\s*=\s*({.*?});",
    r'"pals"\s*:\s*\[(.*?)\]',
    r"palData\s*=\s*({.*?});",
    r"const\s+pals\s*=\s*(\[.*?\]);",
]

for pattern in patterns:
    matches = re.findall(pattern, html, re.DOTALL)
    if matches:
        print(f"Found with pattern: {pattern[:50]}")
        print(
            matches[0][:500] if isinstance(matches[0], str) else str(matches[0])[:500]
        )
        break
else:
    # Look for any script with "Lamball" or "combi"
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        if script.string and (
            "Anubis" in script.string or "combi" in script.string.lower()
        ):
            print(f"Found script with pal data, len={len(script.string)}")
            # extract JSON-like fragments
            idx = script.string.find("Anubis")
            if idx > 0:
                print(script.string[max(0, idx - 100) : idx + 200])
            break
    else:
        print("No pal data found in JS. Trying alternative approach...")
        # Try: maybe paldb.cc has a simple API or JSON endpoint
        for endpoint in ["/api/pals", "/cn/api/pals", "/data/pals.json"]:
            try:
                r = httpx.get(f"https://paldb.cc{endpoint}", timeout=10)
                print(f"  {endpoint}: HTTP {r.status_code}, len={len(r.text)}")
            except Exception as e:
                print(f"  {endpoint}: {e}")
