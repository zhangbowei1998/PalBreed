"""Probe paldb.cc Breed page HTML structure."""

import httpx
from bs4 import BeautifulSoup

url = "https://paldb.cc/cn/Breed?child=Lamball"
resp = httpx.get(url, follow_redirects=True, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

print("=== select elements ===")
for s in soup.find_all("select"):
    name = s.get("name", "") or s.get("id", "")
    options = s.find_all("option")
    if options:
        vals = [o.get("value", "").rsplit("/", 1)[-1] for o in options[:8]]
        print(f"  select #{name}: {len(options)} options, first: {vals}")

print("\n=== pal-related classes ===")
for cls in ["pal-list", "pal-selector", "pal-grid", "pal-option"]:
    els = soup.select(f'[class*="{cls}"]')
    if els:
        print(f"  .{cls}: {len(els)} elements")

print(f"\n=== first 10 /cn/ links with images ===")
links = soup.select("a[href^='/cn/']")
pal_links = []
for a in links:
    href = a.get("href", "")
    img = a.find("img")
    if img:
        src = img.get("src", "")
        alt = img.get("alt", "").strip()
        # Check for pal icon pattern
        pal_links.append((href.rsplit("/", 1)[-1], alt, src[-50:]))

# show first 10
for pid, alt, src in pal_links[:10]:
    print(f"  {pid:30s} alt={alt:10s} src=...{src}")

print(f"\n=== links without images (categories?) ===")
no_img = [a for a in links if not a.find("img")]
for a in no_img[:10]:
    href = a.get("href", "")
    txt = a.get_text(strip=True)[:40]
    print(f"  {href:40s} text={txt}")

# Check if pal images have a specific pattern
print(f"\n=== image src patterns ===")
img_srcs = set()
for a in links:
    img = a.find("img")
    if img:
        src = img.get("src", "")
        # extract pattern
        if "_icon_normal" in src:
            img_srcs.add("_icon_normal")
        elif "_palwork_" in src:
            img_srcs.add("_palwork_")
        elif "T_icon_" in src:
            img_srcs.add("T_icon_")
        else:
            img_srcs.add("other")
print(f"  Patterns found: {img_srcs}")
print(
    f"  Total links: {len(links)}, with img: {len(pal_links)}, without img: {len(no_img)}"
)
