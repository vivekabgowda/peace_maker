from overpass import run_query, FETCH_RADIUS_M, CENTER_LAT, CENTER_LON
import collections

c = f"{FETCH_RADIUS_M},{CENTER_LAT},{CENTER_LON}"

# 1) Any admin_level 7/8/9/10 relations OR ways
ql1 = f"""
[out:json][timeout:240];
(
  relation["boundary"="administrative"]["admin_level"~"^(7|8|9|10)$"](around:{c});
  way["boundary"="administrative"]["admin_level"~"^(7|8|9|10)$"](around:{c});
);
out tags;
"""
d1 = run_query(ql1)
print("== admin_level 7-10 elements ==", len(d1["elements"]))
for e in d1["elements"][:20]:
    t=e.get("tags",{})
    print("  ", e["type"], t.get("admin_level"), t.get("name"))

# 2) Anything with 'hobli' in name/designation/place
ql2 = f"""
[out:json][timeout:240];
(
  node["name"~"[Hh]obli"](around:{c});
  way["name"~"[Hh]obli"](around:{c});
  relation["name"~"[Hh]obli"](around:{c});
  node["place"="hobli"](around:{c});
  node["designation"~"[Hh]obli"](around:{c});
);
out tags;
"""
d2 = run_query(ql2)
print("== 'hobli' tagged elements ==", len(d2["elements"]))
for e in d2["elements"][:20]:
    t=e.get("tags",{})
    print("  ", e["type"], t.get("place"), t.get("designation"), "|", t.get("name"))

# 3) place node census within circle
ql3 = f"""
[out:json][timeout:240];
node["place"](around:{c});
out tags;
"""
d3 = run_query(ql3)
by=collections.Counter()
for e in d3["elements"]:
    by[e["tags"].get("place","?")]+=1
print("== place=* node counts ==", dict(by))
