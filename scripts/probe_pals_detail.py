"""Find actual pal cards on paldb.cc Pals page."""

import httpx
from bs4 import BeautifulSoup

url = "https://paldb.cc/cn/Pals"
resp = httpx.get(url, follow_redirects=True, timeout=20)
soup = BeautifulSoup(resp.text, "html.parser")

# Look for pal cards — usually divs with images and names
# Common patterns on wiki sites: card, tile, entry, list-item
for cls in ["card", "tile", "pal-card", "pal-tile", "list-item", "entry"]:
    els = soup.select(f'[class*="{cls}"]')
    if els:
        texts = [e.get_text(strip=True)[:50] for e in els[:3]]
        print(f".{cls}: {len(els)} elements. First: {texts}")

# Look for img with pal names in alt
imgs = soup.find_all("img")
pal_imgs = []
for img in imgs:
    alt = (img.get("alt", "") or "").strip()
    src = img.get("src", "") or ""
    # Pal images have specific patterns
    if "_icon_normal" in src and "T_" in src:
        pal_imgs.append((alt, src[-60:]))

print(f"\nPal icon images: {len(pal_imgs)}")
for alt, src in pal_imgs[:10]:
    print(f"  {alt:15s} {src}")

# Also check for links that look like pal pages
import re

pal_link_pat = re.compile(r"/cn/([A-Z][a-z]+[a-zA-Z_]*)")
all_a = soup.find_all("a", href=pal_link_pat)
# Filter out known non-pals
non_pals = {
    "Palpagos_Islands",
    "The_World_Tree",
    "Raid",
    "Humans",
    "Element_Swap",
    "Weight_Increase",
    "Mounts",
    "Glider",
    "Drop_Rate",
    "Party_Buffs",
    "Pal_Stats",
    "Spoiler",
    "Work_Priority",
    "SAN",
    "Partner_Skill",
    "Active_Skills",
    "Passive_Skills",
    "Skill_Fruit",
    "Breed",
    "Pal_Calc",
    "Iv_Calc",
    "Capture_Rate",
    "Pals",
    "Alpha_Pals",
    "Rampaging",
    "Boss",
    "Tower",
    "Building",
    "Technology",
    "Item",
    "Pal",
    "Sphere",
    "Sphere_Module",
    "Weapon",
    "Armor",
    "Accessory",
    "Material",
    "Consumable",
    "Ammo",
    "Ingredient",
    "Key_Items",
    "Food",
    "Infrastructure",
    "Lighting",
    "Foundations",
    "Defenses",
    "Furniture",
    "Other",
    "Storage",
    "Production",
    "Gear",
    "Schematic",
    # work types
    "Kindling",
    "Watering",
    "Planting",
    "Generating_Electricity",
    "Handiwork",
    "Gathering",
    "Lumbering",
    "Mining",
    "Medicine_Production",
    "Cooling",
    "Transporting",
    "Farming",
}
real_pals = [
    (a["href"].rsplit("/", 1)[-1], a.get_text(strip=True)[:20])
    for a in all_a
    if a["href"].rsplit("/", 1)[-1] not in non_pals
]

print(f"\nPotential pal links: {len(real_pals)}")
for pid, txt in real_pals[:20]:
    print(f"  /cn/{pid:30s} {txt}")
if len(real_pals) > 20:
    print(f"  ... ({len(real_pals)} total)")
