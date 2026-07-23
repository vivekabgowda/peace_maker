"""Fetch all OSM source data for the Tiptur 40 km publication map.

Layers saved to ../data/tiptur_raw.gpkg:
  - boundaries_l5  (districts)
  - boundaries_l6  (taluks)
  - places         (town/village/hamlet points)
  - roads          (classified highway linework)
Everything is stored in EPSG:4326 (raw). Clipping/projection happens at render time.
"""
import os
import sys
import time
import geopandas as gpd
import osmnx as ox

from overpass import CENTER_LAT, CENTER_LON, FETCH_RADIUS_M

ox.settings.requests_timeout = 300
ox.settings.overpass_rate_limit = True
ox.settings.log_console = False
ox.settings.use_cache = True
ox.settings.cache_folder = os.path.join(os.path.dirname(__file__), "..", "data", "osm_cache")

CENTER = (CENTER_LAT, CENTER_LON)
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
GPKG = os.path.join(DATA, "tiptur_raw.gpkg")

ROAD_CLASSES = [
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
    "living_street", "road",
]


def keep_cols(gdf, cols):
    """Return gdf with only the requested attribute cols that exist, plus geometry."""
    have = [c for c in cols if c in gdf.columns]
    out = gdf[have + ["geometry"]].copy()
    # flatten any list-valued cells (OSM multi-value tags) to comma strings
    for c in have:
        out[c] = out[c].apply(lambda v: ", ".join(v) if isinstance(v, list) else v)
    return out


def fetch_boundaries():
    print("[boundaries] fetching admin_level 5 + 6 ...", flush=True)
    g = ox.features_from_point(
        CENTER,
        tags={"boundary": "administrative", "admin_level": ["5", "6"]},
        dist=FETCH_RADIUS_M,
    )
    g = g[g.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    g = g.reset_index()
    cols = ["osmid", "name", "name:en", "admin_level", "wikidata", "ref"]
    l5 = keep_cols(g[g["admin_level"] == "5"], cols)
    l6 = keep_cols(g[g["admin_level"] == "6"], cols)
    print(f"[boundaries] districts(L5)={len(l5)}  taluks(L6)={len(l6)}", flush=True)
    l5.to_file(GPKG, layer="boundaries_l5", driver="GPKG")
    l6.to_file(GPKG, layer="boundaries_l6", driver="GPKG")
    print("[boundaries] taluk names:", sorted(l6["name"].dropna().tolist()), flush=True)


def fetch_places():
    print("[places] fetching town/village/hamlet ...", flush=True)
    g = ox.features_from_point(
        CENTER,
        tags={"place": ["town", "village", "hamlet", "suburb"]},
        dist=FETCH_RADIUS_M,
    )
    g = g[g.geometry.type == "Point"].copy().reset_index()
    cols = ["osmid", "name", "name:en", "name:kn", "place", "population", "wikidata"]
    p = keep_cols(g, cols)
    print(f"[places] points={len(p)}  by type:\n{p['place'].value_counts()}", flush=True)
    p.to_file(GPKG, layer="places", driver="GPKG")


def fetch_roads():
    print("[roads] fetching classified highways (may take a while) ...", flush=True)
    cf = '["highway"~"^(' + "|".join(ROAD_CLASSES) + ')$"]'
    g = ox.features_from_point(
        CENTER,
        tags={"highway": ROAD_CLASSES},
        dist=FETCH_RADIUS_M,
    )
    g = g[g.geometry.type.isin(["LineString", "MultiLineString"])].copy().reset_index()
    cols = ["osmid", "highway", "name", "name:en", "ref", "int_ref", "nat_ref",
            "reg_ref", "network", "lanes", "surface", "oneway"]
    r = keep_cols(g, cols)
    print(f"[roads] segments={len(r)}  by class:\n{r['highway'].value_counts()}", flush=True)
    r.to_file(GPKG, layer="roads", driver="GPKG")


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    t0 = time.time()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "boundaries"):
        fetch_boundaries()
    if which in ("all", "places"):
        fetch_places()
    if which in ("all", "roads"):
        fetch_roads()
    print(f"[done] {which} in {time.time()-t0:.0f}s -> {GPKG}", flush=True)
