"""Extract hobli lists for in-frame taluks from Wikipedia (authoritative-ish),
then match each hobli headquarters to an OSM place point for coordinates.

Wikipedia is used only to enumerate hobli NAMES per taluk; all coordinates come
from real OSM place nodes (no fabricated positions). Any hobli whose HQ cannot be
matched to an OSM point is reported and dropped (never given a made-up location).
"""
import re
import json
import requests

UA = {"User-Agent": "tiptur-gis-map/1.0 (rajeshyad20015@gmail.com)"}
API = "https://en.wikipedia.org/w/api.php"

# Candidate Wikipedia article titles for taluks intersecting the 40 km circle
TALUK_ARTICLES = [
    "Tiptur", "Chiknayakanhalli", "Gubbi", "Turuvekere", "Arsikere",
    "Kadur", "Sira, Karnataka", "Hosadurga", "Nagamangala",
    "Kunigal", "Channarayapatna", "Belur, Karnataka", "Tumkur district",
]


def get_wikitext(title):
    r = requests.get(API, params={
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "redirects": 1,
    }, headers=UA, timeout=40)
    j = r.json()
    if "parse" not in j:
        return None
    return j["parse"]["wikitext"]["*"]


def find_hoblis(text):
    """Heuristically pull hobli names from a wiki article's text."""
    found = set()
    if not text:
        return found
    # Pattern A: explicit "X hobli" mentions
    for m in re.finditer(r"([A-Z][A-Za-z .()\-]{2,40}?)\s+[Hh]obli", text):
        found.add(m.group(1).strip())
    # Pattern B: a "Hoblies"/"Hobli" section with a bullet/comma list
    sec = re.search(r"(?:==+\s*Hobli(?:e?s)?\s*==+)(.+?)(?:\n==|\Z)", text, re.S)
    if sec:
        body = sec.group(1)
        for line in re.split(r"[\n,]", body):
            line = re.sub(r"[\*\#\[\]']", "", line).strip()
            line = re.sub(r"\(.*?\)", "", line).strip()
            if 2 < len(line) < 40 and re.match(r"^[A-Za-z][A-Za-z .\-]+$", line):
                found.add(line)
    return found


if __name__ == "__main__":
    result = {}
    for title in TALUK_ARTICLES:
        try:
            txt = get_wikitext(title)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {title}: {e}")
            continue
        hoblis = sorted(find_hoblis(txt))
        result[title] = hoblis
        print(f"{title}: {hoblis}")
    with open("../data/hoblis_wikipedia_raw.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nsaved ../data/hoblis_wikipedia_raw.json")
