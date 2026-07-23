"""Process raw OSM data into clean, projected, classified layers for rendering.

Output: ../data/tiptur_processed.gpkg  (EPSG:32643 / UTM 43N)
  layers: circle40, frame, districts, taluks, roads, places, hoblis
Also writes ../data/label_report.json summarising counts.
"""
import os
import re
import json
import unicodedata
import difflib
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import unary_union

from overpass import CENTER_LAT, CENTER_LON, RADIUS_M

RAW = "../data/tiptur_raw.gpkg"
OUT = "../data/tiptur_processed.gpkg"
UTM = 32643  # WGS84 / UTM zone 43N — appropriate for ~76.5E, minimal distortion

# ---- curated authoritative hobli headquarters per taluk (revenue circles) ----
# Names are matched to real OSM place points; unmatched entries are dropped &
# reported (never given fabricated coordinates). Sources: Karnataka revenue
# administration; Gubbi set cross-checked against Wikipedia ("six hoblis").
HOBLI_HQ = {
    "Tipaturu taluk": ["Tiptur", "Honnavalli", "Nonavinakere", "Kibbanahalli"],
    "Chikkanayakanahalli taluk": ["Chikkanayakanahalli", "Huliyar", "Handanakere",
                                   "Dandinashivara", "Kandikere", "Shettikere"],
    "Gubbi taluk": ["Gubbi", "Hagalavadi", "Chelur", "Nittur", "Kadaba", "C.S.Pura"],
    "Turuvekere taluk": ["Turuvekere", "Mayasandra", "Dabbeghatta", "Dandinakuruke"],
    "Arasikere taluku": ["Arasikere", "Javagal", "Banavara", "Gandasi", "Kanakatte"],
    "Kaduru taluk": ["Kadur", "Yagati", "Panchanahalli", "Sakharayapatna"],
    "Sira taluk": ["Sira", "Kallambella", "Gowdagere"],
    "Nagamangala taluk": ["Nagamangala", "Bellur", "Honakere"],
}


def norm(s):
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"\b(taluk|taluku|kasaba|hobli)\b", "", s)
    s = re.sub(r"[^a-z]", "", s)
    return s


def dissolve_named(gdf):
    """Collapse relation+member duplicates: dissolve polygons by name."""
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["nm"] = gdf["name"].fillna("?")
    diss = gdf.dissolve(by="nm", aggfunc="first").reset_index(drop=False)
    return diss


def classify_road(row):
    ref = str(row.get("ref") or "")
    hw = row.get("highway") or ""
    if re.search(r"\bNH", ref) or re.match(r"NH", ref):
        return "national_highway"
    if re.search(r"\bSH", ref) or re.match(r"SH", ref):
        return "state_highway"
    if hw in ("motorway", "motorway_link", "trunk", "trunk_link"):
        return "national_highway"
    if hw in ("primary", "primary_link"):
        return "state_highway"
    if hw in ("secondary", "secondary_link"):
        return "district_road"        # Major District Road (MDR)
    if hw in ("tertiary", "tertiary_link"):
        return "connecting_road"       # Other District / connecting roads
    if hw in ("unclassified",):
        return "rural_road"
    return "village_road"              # residential, living_street, road


def main():
    center_ll = gpd.GeoSeries([Point(CENTER_LON, CENTER_LAT)], crs=4326).to_crs(UTM)
    cx, cy = center_ll.geometry.x[0], center_ll.geometry.y[0]
    circle = center_ll.buffer(RADIUS_M).iloc[0]
    circle_gdf = gpd.GeoDataFrame({"r_km": [40]}, geometry=[circle], crs=UTM)
    # square neatline frame = circle bbox with small margin
    margin = 1500
    from shapely.geometry import box
    minx, miny, maxx, maxy = circle.bounds
    frame_geom = box(minx - margin, miny - margin, maxx + margin, maxy + margin)
    frame = gpd.GeoDataFrame({"id": [1]}, geometry=[frame_geom], crs=UTM)
    report = {"center_utm": [cx, cy]}

    # ---- boundaries ----
    l5 = gpd.read_file(RAW, layer="boundaries_l5").to_crs(UTM)
    l6 = gpd.read_file(RAW, layer="boundaries_l6").to_crs(UTM)
    districts = dissolve_named(l5)
    taluks = dissolve_named(l6)
    # clip to circle for on-map fills/lines
    districts_c = gpd.clip(districts, circle)
    taluks_c = gpd.clip(taluks, circle)
    report["districts"] = sorted(districts["name"].dropna().unique().tolist())
    report["taluks"] = sorted(taluks["name"].dropna().unique().tolist())

    # ---- roads ----
    roads = gpd.read_file(RAW, layer="roads").to_crs(UTM)
    roads["cls"] = roads.apply(classify_road, axis=1)
    roads_c = gpd.clip(roads, circle)
    roads_c = roads_c[roads_c.geometry.length > 0]
    report["roads_by_class"] = roads_c["cls"].value_counts().to_dict()

    # ---- places ----
    places = gpd.read_file(RAW, layer="places").to_crs(UTM)

    def pick_label(row):
        # prefer the common ASCII spelling in `name`; fall back to name:en
        for key in ("name", "name:en"):
            v = row.get(key)
            if isinstance(v, str) and v.strip() and v.isascii():
                return v.strip()
        for key in ("name:en", "name"):
            v = row.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    places["label"] = places.apply(pick_label, axis=1)
    places_c = gpd.clip(places, circle).copy()
    places_c = places_c[places_c["label"].notna()]
    report["places_by_type"] = places_c["place"].value_counts().to_dict()

    # ---- hoblis: match curated HQ names to real OSM place points ----
    # index every place by norm() of all its name variants -> geometry
    place_norm = {}
    for _, r in places.iterrows():
        for key in ("label", "name", "name:en"):
            v = r.get(key)
            if isinstance(v, str) and v.strip():
                place_norm.setdefault(norm(v), r.geometry)
    place_keys = list(place_norm.keys())
    hobli_rows = []
    unmatched = []
    for taluk, hqs in HOBLI_HQ.items():
        for hq in hqs:
            key = norm(hq)
            geom = place_norm.get(key)
            if geom is None:
                cand = difflib.get_close_matches(key, place_keys, n=1, cutoff=0.86)
                if cand:
                    geom = place_norm[cand[0]]
            if geom is None:
                unmatched.append(f"{hq} ({taluk})")
                continue
            hobli_rows.append({"hobli": hq, "taluk": taluk, "geometry": geom})
    hoblis = gpd.GeoDataFrame(hobli_rows, crs=UTM)
    hoblis_c = gpd.clip(hoblis, circle).drop_duplicates(subset="hobli")
    report["hoblis_matched"] = hoblis_c["hobli"].tolist()
    report["hoblis_unmatched_dropped"] = unmatched

    # Flag generic places that coincide with a hobli HQ (by name OR proximity)
    # so the renderer does not double-label them (e.g. "Huliyar" vs "Huliyaru").
    hobli_norms = {norm(h) for h in hoblis_c["hobli"]}
    if len(hoblis_c):
        hobli_area = unary_union(hoblis_c.geometry.values).buffer(400)
    else:
        hobli_area = Point(0, 0).buffer(0)
    places_c["is_hobli"] = places_c.apply(
        lambda r: (norm(r["label"]) in hobli_norms) or hobli_area.contains(r.geometry),
        axis=1)

    # ---- write ----
    if os.path.exists(OUT):
        os.remove(OUT)
    circle_gdf.to_file(OUT, layer="circle40", driver="GPKG")
    frame.to_file(OUT, layer="frame", driver="GPKG")
    districts_c.to_file(OUT, layer="districts", driver="GPKG")
    taluks_c.to_file(OUT, layer="taluks", driver="GPKG")
    roads_c.to_file(OUT, layer="roads", driver="GPKG")
    places_c.to_file(OUT, layer="places", driver="GPKG")
    if len(hoblis_c):
        hoblis_c.to_file(OUT, layer="hoblis", driver="GPKG")

    with open("../data/label_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
