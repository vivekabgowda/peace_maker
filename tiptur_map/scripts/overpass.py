"""Robust Overpass API client with endpoint rotation and retry/backoff.

Used by all data-fetching steps of the Tiptur publication map pipeline.
"""
import time
import json
import sys
import requests

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]

UA = "tiptur-gis-map/1.0 (rajeshyad20015@gmail.com)"

# Tiptur town centre (Nominatim, OSM), WGS84
CENTER_LAT = 13.2585750
CENTER_LON = 76.4737675
RADIUS_M = 40000          # 40 km analytical radius
FETCH_RADIUS_M = 46000    # slightly larger fetch buffer so edge geometry is complete


def run_query(ql: str, retries: int = 6, timeout: int = 300) -> dict:
    """POST an Overpass QL query, rotating endpoints and backing off on failure."""
    last_err = None
    for attempt in range(retries):
        ep = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            r = requests.post(
                ep,
                data={"data": ql},
                headers={"User-Agent": UA},
                timeout=timeout,
            )
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            # Overpass returns 429/504 or an HTML error page when overloaded
            last_err = f"{ep} -> HTTP {r.status_code}: {r.text[:200]!r}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{ep} -> {e!r}"
        wait = min(4 * (2 ** attempt), 60)
        print(f"  [overpass] attempt {attempt+1} failed ({last_err}); retin {wait}s",
              file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"Overpass query failed after {retries} attempts: {last_err}")


if __name__ == "__main__":
    # Self-test / admin-level discovery probe
    ql = f"""
[out:json][timeout:240];
relation["boundary"="administrative"](around:{FETCH_RADIUS_M},{CENTER_LAT},{CENTER_LON});
out tags;
"""
    d = run_query(ql)
    import collections
    by = collections.defaultdict(list)
    for e in d["elements"]:
        t = e.get("tags", {})
        by[t.get("admin_level", "?")].append(t.get("name:en") or t.get("name") or "?")
    print("total admin relations:", len(d["elements"]))
    for lvl in sorted(by, key=lambda x: (x != "?", x)):
        names = by[lvl]
        print(f"admin_level={lvl}  count={len(names)}  e.g. {sorted(set(names))[:14]}")
