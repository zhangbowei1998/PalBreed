"""Diagnose work suitability parsing on Anubis page."""

from bs4 import BeautifulSoup
from pathlib import Path
import re

html = Path("data/raw/pages/Anubis.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "html.parser")

# Find work type links and their Lv values
work_hrefs = [
    "Handiwork",
    "Mining",
    "Transporting",
    "Kindling",
    "Watering",
    "Planting",
    "Generating_Electricity",
    "Gathering",
    "Lumbering",
    "Cooling",
    "Medicine_Production",
    "Farming",
]

for a_tag in soup.find_all("a"):
    href = a_tag.get("href", "")
    if href not in work_hrefs:
        continue
    wt_text = a_tag.get_text(strip=True)
    # The Lv is in a sibling <div>:  <div><span>Lv</span>6</div>
    parent = a_tag.find_parent("div")
    if parent:
        # find the next div that has Lv text
        for sib in parent.find_next_siblings("div"):
            sib_text = sib.get_text(strip=True)
            m = re.search(r"Lv\s*(\d+)", sib_text)
            if m:
                print(f"  {wt_text}: Lv{m.group(1)} (via sibling)")
                break
        else:
            # try regex on parent text
            ptext = parent.get_text()
            m = re.search(r"Lv\s*(\d+)", ptext)
            if m:
                print(f"  {wt_text}: Lv{m.group(1)} (via parent text)")
            else:
                print(f"  {wt_text}: NOT FOUND")

# Now check what the parser actually receives
text = soup.get_text(separator="\n")
idx = text.find("手工作业")
if idx >= 0:
    chunk = text[idx : idx + 100]
    print(f"\nget_text around 手工作业: {repr(chunk)}")
