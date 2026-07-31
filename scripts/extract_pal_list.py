"""Extract pal list from paldb.cc /cn/Pals page image filenames."""

import re
import httpx
from bs4 import BeautifulSoup

url = "https://paldb.cc/cn/Pals"
resp = httpx.get(url, follow_redirects=True, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

# Find all img with _icon_normal (these are pal icons)
pals = []
for img in soup.find_all("img"):
    src = img.get("src", "")
    if "_icon_normal" not in src or "T_icon_palwork" in src:
        continue
    # Extract internal ID from filename: T_SheepBall_icon_normal → SheepBall
    match = re.search(r"T_(\w+?)_icon_normal", src)
    if not match:
        continue
    internal_id = match.group(1)
    # Find parent <a> tag for the URL name
    parent_a = img.find_parent("a")
    href = parent_a.get("href", "") if parent_a else ""
    url_name = href.rsplit("/", 1)[-1] if href else ""
    alt = img.get("alt", "").strip()

    # Extract number from text near the image
    parent_div = img.find_parent("div") or img.find_parent("span")
    text_nearby = parent_div.get_text() if parent_div else ""
    num_match = re.search(r"#?0*(\d{1,3})", text_nearby)
    number = int(num_match.group(1)) if num_match else 0

    # cn_name is usually in the alt text or nearby text
    cn_name = alt if alt and not alt.startswith("T") else ""
    if not cn_name and parent_div:
        # try to extract Chinese name
        text = parent_div.get_text(strip=True)
        # Chinese chars are in Unicode range \u4e00-\u9fff
        cn_match = re.search(r"[\u4e00-\u9fff]+", text)
        if cn_match:
            cn_name = cn_match.group()

    pals.append(
        {
            "internal_id": internal_id,
            "url_name": url_name,
            "cn_name": cn_name,
            "number": number,
        }
    )

print(f"Found {len(pals)} pals from images:")
for p in pals[:20]:
    print(
        f"  #{p['number']:3d} | {p['internal_id']:25s} | URL: {p['url_name']:25s} | {p['cn_name']}"
    )
print(f"  ... ({len(pals)} total)")

# Check: do we have unique URL names or all empty?
url_names = [p["url_name"] for p in pals if p["url_name"]]
print(f"\nPals with URL names: {len(url_names)}")
print(f"Unique URL names: {len(set(url_names))}")
if url_names:
    print(f"Sample: {url_names[:5]}")
