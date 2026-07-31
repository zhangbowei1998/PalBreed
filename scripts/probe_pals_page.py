"""Probe paldb.cc /cn/Pals page for pal listing."""

import re
import httpx
from bs4 import BeautifulSoup

url = "https://paldb.cc/cn/Pals"
resp = httpx.get(url, follow_redirects=True, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

print(f"Page title: {soup.title.string if soup.title else 'N/A'}")
print(f"Page length: {len(resp.text)} chars")

# find all pal links
pal_pattern = re.compile(r"/cn/([A-Z][a-zA-Z_]+)$")
all_links = soup.find_all("a", href=pal_pattern)
pals = []
for a in all_links:
    href = a["href"]
    pid = href.rsplit("/", 1)[-1]
    img = a.find("img")
    alt = img.get("alt", "").strip() if img else ""
    txt = a.get_text(strip=True)[:20]
    if pid not in (
        "Breed",
        "Building",
        "Technology",
        "Item",
        "Pals",
        "Alpha_Pals",
        "Rampaging",
        "Pal_Calc",
        "Iv_Calc",
        "Capture_Rate",
        "Boss",
        "Tower",
    ):
        pals.append((pid, alt or txt))

print(f"\nFound {len(pals)} pal links:")
for pid, name in pals[:30]:
    print(f"  {pid:30s} {name}")
print(f"  ... ({len(pals)} total)")

# Check for data attributes or script tags with pal data
scripts = soup.find_all("script")
for s in scripts:
    if s.string and "pals" in s.string.lower() and len(s.string) > 500:
        print(f"\n=== Script with pal data ({len(s.string)} chars) ===")
        print(s.string[:500])
        break
