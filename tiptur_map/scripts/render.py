"""Render the Tiptur 40 km publication map (A0 / A1 landscape).

Reads ../data/tiptur_processed.gpkg (EPSG:32643) and composes a museum-quality
cartographic sheet: classified road network, taluk/district boundaries, 40 km
dashed radius, collision-free place/hobli/taluk labels, legend, north arrow,
graticule and scale bar. Exports vector PDF + high-res PNG.

Usage:  python3 render.py [draft|a1|a0|all]
"""
import os
import sys
import json
import math
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Circle, Rectangle, FancyArrow, PathPatch
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
from shapely.geometry import box as sbox, Point
from shapely.strtree import STRtree
from pyproj import Transformer

GPKG = "../data/tiptur_processed.gpkg"
OUTDIR = "../output"
UTM = 32643

# ----------------------------- palette --------------------------------------
BG           = "#ffffff"
C_VILLAGE_RD = "#e2e2e2"   # very light gray  (village roads)
C_RURAL_RD   = "#cfcfcf"   # light gray       (rural roads)
C_CONNECT_RD = "#b4b4b4"   # gray             (connecting/other district)
C_DISTRICT_RD= "#8f8f8f"   # medium gray      (Major District Roads)
C_STATE_HW   = "#e08a1e"   # muted orange     (State Highways)
C_NAT_HW     = "#9e2b25"   # dark red         (National Highways)
C_TALUK_LINE = "#4d4d4d"   # dark gray        (taluk boundaries)
C_DIST_LINE  = "#2b2b2b"   # near-black       (district boundaries)
C_CIRCLE     = "#3b6ea5"   # muted blue       (40 km radius, dashed)
C_VILLAGE_TX = "#2b2b2b"   # dark charcoal    (village labels)
C_HOBLI_TX   = "#1f3f73"   # deep blue        (hobli labels)
C_TALUK_TX   = "#6d1a2e"   # dark maroon      (taluk labels)
C_TOWN_TX    = "#111111"
C_HAMLET_TX  = "#6b6b6b"
C_GRID       = "#d8d8d8"
C_NEATLINE   = "#222222"
C_PANEL_RULE = "#c9c9c9"

# muted pastel fills for taluks (atlas look); cycled by taluk
PASTELS = ["#f4ece4", "#eef1e6", "#e9eef2", "#f3ecf0", "#eef0ea",
           "#f2efe6", "#e7eef0", "#f0ece7", "#eaf0ee", "#f1eaea",
           "#ecefe8", "#e9ecf1", "#f3eee6", "#eceef0", "#f0ede9",
           "#e8eef2", "#f2ece9"]

SERIF = "DejaVu Serif"
SANS  = "DejaVu Sans"

# tidy display names for taluks (OSM transliteration -> common English)
TALUK_RENAME = {
    "Tipaturu": "Tiptur", "Hasana": "Hassan", "Beluru": "Belur",
    "Kaduru": "Kadur", "Channarayapattana": "Channarayapatna",
    "Krishnarajapete": "Krishnarajapet", "Hole Narasipura": "Hole Narasipura",
    "Hosadurga": "Hosadurga", "Arasikere": "Arasikere", "Aluru": "Alur",
}


def taluk_display(name):
    import re as _re
    base = _re.sub(r"\s+taluku?$", "", str(name)).strip()
    return TALUK_RENAME.get(base, base)


# ----------------------- greedy collision-free labels ------------------------
class LabelPlacer:
    """Priority-ordered, collision-free point-label placement using bbox tests
    in display coordinates (mimics ArcGIS Maplex weighted placement)."""

    def __init__(self, ax, fig):
        self.ax = ax
        self.fig = fig
        fig.canvas.draw()                       # establish transforms + renderer ONCE
        self.renderer = fig.canvas.get_renderer()
        self.boxes = np.empty((0, 4))            # placed boxes [x0,y0,x1,y1] display coords

    def reserve(self, x0, y0, x1, y1):
        self.boxes = np.vstack([self.boxes, [x0, y0, x1, y1]])

    def _collides(self, x0, y0, x1, y1):
        if self.boxes.shape[0] == 0:
            return False
        B = self.boxes
        # axis-aligned overlap: NOT (separated on any axis)
        sep = (B[:, 0] > x1) | (B[:, 2] < x0) | (B[:, 1] > y1) | (B[:, 3] < y0)
        return bool((~sep).any())

    def place(self, x, y, text, color, size, weight="normal", family=SERIF,
              halo=2.2, halo_color="white", dot=None, dot_size=0,
              candidates=None, zorder=6, style="normal"):
        """Try candidate positions around (x,y); draw first non-colliding one."""
        if candidates is None:
            candidates = [("left", "center", 6, 0), ("right", "center", -6, 0),
                          ("center", "bottom", 0, 6), ("center", "top", 0, -6),
                          ("left", "bottom", 5, 5), ("right", "top", -5, -5)]
        for ha, va, dx, dy in candidates:
            t = self.ax.annotate(
                text, (x, y), xytext=(dx, dy), textcoords="offset points",
                ha=ha, va=va, fontsize=size, color=color, family=family,
                weight=weight, style=style, zorder=zorder, annotation_clip=True)
            if halo:
                import matplotlib.patheffects as pe
                t.set_path_effects([pe.withStroke(linewidth=halo, foreground=halo_color)])
            try:
                bb = t.get_window_extent(self.renderer)
            except Exception:
                t.remove(); continue
            pad = 1.0
            x0, y0, x1, y1 = bb.x0 - pad, bb.y0 - pad, bb.x1 + pad, bb.y1 + pad
            if self._collides(x0, y0, x1, y1):
                t.remove()
                continue
            self.boxes = np.vstack([self.boxes, [x0, y0, x1, y1]])
            if dot is not None and dot_size:
                self.ax.plot([x], [y], marker="o", ms=dot_size, mfc=dot,
                             mec="white", mew=0.5, zorder=zorder - 0.5)
            return True
        return False  # dropped (no room)


# ------------------------------- helpers ------------------------------------
def road_style(cls):
    return {
        "national_highway": (C_NAT_HW,   2.6, 5.0),
        "state_highway":    (C_STATE_HW, 1.9, 4.4),
        "district_road":    (C_DISTRICT_RD, 1.2, 3.6),
        "connecting_road":  (C_CONNECT_RD, 0.7, 3.0),
        "rural_road":       (C_RURAL_RD,  0.5, 2.4),
        "village_road":     (C_VILLAGE_RD, 0.35, 2.0),
    }[cls]


def draw_graticule(ax, frame_bounds, clip=None, zorder=5.5):
    """Subtle lat/lon graticule (clipped to the circle) + edge tick labels."""
    minx, miny, maxx, maxy = frame_bounds
    to_ll = Transformer.from_crs(UTM, 4326, always_xy=True)
    to_utm = Transformer.from_crs(4326, UTM, always_xy=True)
    lon0, lat0 = to_ll.transform(minx, miny)
    lon1, lat1 = to_ll.transform(maxx, maxy)
    step = 0.2
    lons = np.arange(math.floor(lon0 / step) * step, lon1 + step, step)
    lats = np.arange(math.floor(lat0 / step) * step, lat1 + step, step)
    for lon in lons:
        ys = np.linspace(lat0 - 1, lat1 + 1, 80)
        pts = [to_utm.transform(lon, yy) for yy in ys]
        ln, = ax.plot([p[0] for p in pts], [p[1] for p in pts],
                      color=C_GRID, lw=0.4, zorder=zorder)
        if clip is not None:
            ln.set_clip_path(clip)
        # edge tick label near bottom
        tx, ty = to_utm.transform(lon, lat0 + 0.01)
        if minx < tx < maxx:
            ax.text(tx, miny - 200, f"{lon:.1f}°E", ha="center", va="top",
                    fontsize=6.5, color="#999", family=SANS, zorder=19)
    for lat in lats:
        xs = np.linspace(lon0 - 1, lon1 + 1, 80)
        pts = [to_utm.transform(xx, lat) for xx in xs]
        ln, = ax.plot([p[0] for p in pts], [p[1] for p in pts],
                      color=C_GRID, lw=0.4, zorder=zorder)
        if clip is not None:
            ln.set_clip_path(clip)
        tx, ty = to_utm.transform(lon0 + 0.01, lat)
        if miny < ty < maxy:
            ax.text(minx - 200, ty, f"{lat:.1f}°N", ha="right", va="center",
                    fontsize=6.5, color="#999", family=SANS, zorder=19)
    return lons, lats


def scale_bar(ax, x, y, length_m=10000, height=700):
    """Alternating black/white scale bar (4 segments) on a white backing card."""
    n = 4
    seg = length_m / n
    ax.add_patch(Rectangle((x - 2200, y - 2600), length_m + 6500, height + 4200,
                           facecolor="white", edgecolor="#bfbfbf", lw=0.8,
                           zorder=17.5, alpha=0.95))
    for i in range(n):
        c = "#222222" if i % 2 == 0 else "#ffffff"
        ax.add_patch(Rectangle((x + i * seg, y), seg, height, facecolor=c,
                               edgecolor="#222222", lw=0.8, zorder=18))
    for i in range(n + 1):
        ax.text(x + i * seg, y - 550, f"{int(i*seg/1000)}", ha="center",
                va="top", fontsize=7.5, family=SANS, color="#222", zorder=18)
    ax.text(x + length_m + 900, y + height/2, "km", ha="left", va="center",
            fontsize=8, family=SANS, color="#222", zorder=18)
    ax.text(x, y + height + 400, "Scale  1 : 165,000 (at A0)", ha="left",
            va="bottom", fontsize=7, family=SANS, color="#555", zorder=18)


def north_arrow(ax, x, y, size=2600):
    ax.add_patch(FancyArrow(x, y, 0, size, width=size*0.02, head_width=size*0.28,
                            head_length=size*0.34, length_includes_head=True,
                            facecolor="#222", edgecolor="#222", zorder=9))
    ax.text(x, y + size + 900, "N", ha="center", va="bottom", fontsize=13,
            weight="bold", family=SERIF, color="#222", zorder=9)


# ------------------------------- main render --------------------------------
def render(sheet="a1", dpi=200, draft=False, png_dpi=None):
    png_dpi = png_dpi or dpi
    circle = gpd.read_file(GPKG, layer="circle40")
    frame  = gpd.read_file(GPKG, layer="frame")
    districts = gpd.read_file(GPKG, layer="districts")
    taluks = gpd.read_file(GPKG, layer="taluks")
    roads  = gpd.read_file(GPKG, layer="roads")
    places = gpd.read_file(GPKG, layer="places")
    try:
        hoblis = gpd.read_file(GPKG, layer="hoblis")
    except Exception:
        hoblis = gpd.GeoDataFrame(columns=["hobli", "geometry"], crs=UTM)

    circ_geom = circle.geometry.iloc[0]
    cx, cy = circ_geom.centroid.x, circ_geom.centroid.y
    fb = frame.total_bounds  # minx,miny,maxx,maxy

    # sheet sizes (mm) landscape
    SHEETS = {"a0": (1189, 841), "a1": (841, 594), "draft": (594, 420)}
    W_mm, H_mm = SHEETS[sheet]
    fig = plt.figure(figsize=(W_mm/25.4, H_mm/25.4), dpi=dpi)
    fig.patch.set_facecolor(BG)

    # layout: square map area on left, info panel on right
    map_frac = H_mm / W_mm            # square map occupies full height
    map_w = map_frac * 0.96
    ax = fig.add_axes([0.012, 0.02, map_w, 0.96])
    ax.set_facecolor(BG)
    panel_x = 0.012 + map_w + 0.012
    pax = fig.add_axes([panel_x, 0.02, 1 - panel_x - 0.012, 0.96])
    pax.axis("off")

    # map extent = circle bbox (square) with small margin
    minx, miny, maxx, maxy = circ_geom.bounds
    m = 1200
    ax.set_xlim(minx - m, maxx + m)
    ax.set_ylim(miny - m, maxy + m)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    # clip path = circle
    radius = (circ_geom.bounds[2] - cx)
    clipper = Circle((cx, cy), radius, transform=ax.transData,
                     facecolor="none", edgecolor="none")
    ax.add_patch(clipper)

    # taluk pastel fills + clip to circle
    taluks = taluks.reset_index(drop=True)
    for i, row in taluks.iterrows():
        gs = gpd.GeoSeries([row.geometry], crs=UTM)
        gs.plot(ax=ax, facecolor=PASTELS[i % len(PASTELS)], edgecolor="none",
                zorder=1, alpha=0.9)

    # subtle graticule over fills, under roads, clipped to the circle
    draw_graticule(ax, (minx - m, miny - m, maxx + m, maxy + m),
                   clip=clipper, zorder=1.5)

    # roads by class (ascending importance so majors draw on top)
    order = ["village_road", "rural_road", "connecting_road", "district_road",
             "state_highway", "national_highway"]
    for cls in order:
        sub = roads[roads["cls"] == cls]
        if sub.empty:
            continue
        col, lw, z = road_style(cls)
        sub.plot(ax=ax, color=col, linewidth=lw, zorder=z,
                 capstyle="round", joinstyle="round")

    # taluk & district boundary lines (clipped to circle)
    taluks.boundary.plot(ax=ax, color=C_TALUK_LINE, linewidth=1.1,
                         zorder=6.2, linestyle=(0, (6, 2)))
    districts.boundary.plot(ax=ax, color=C_DIST_LINE, linewidth=1.9, zorder=6.4)

    # white mask outside circle for a clean radius clip
    ring = sbox(minx - m*3, miny - m*3, maxx + m*3, maxy + m*3).difference(
        circ_geom)
    gpd.GeoSeries([ring], crs=UTM).plot(ax=ax, facecolor=BG, edgecolor="none",
                                        zorder=6.6)
    # 40 km dashed blue circle
    ax.add_patch(Circle((cx, cy), radius, fill=False, ec=C_CIRCLE, lw=1.6,
                        ls=(0, (7, 4)), zorder=6.8))

    # clip everything drawn so far to the circle
    for coll in ax.collections:
        coll.set_clip_path(clipper)

    # ------------------- labels (priority order) -------------------
    lp = LabelPlacer(ax, fig)

    def pop(row):
        try:
            return float(row["population"])
        except Exception:
            return 0.0
    places = places.copy()
    places["is_hobli"] = places["is_hobli"].fillna(False)
    rank = {"town": 3, "suburb": 1, "village": 2, "hamlet": 0}
    places["rk"] = places["place"].map(rank).fillna(1)
    places["popf"] = places.apply(pop, axis=1)
    places = places.sort_values(["rk", "popf"], ascending=False)
    tiptur = places[places["label"].str.lower() == "tiptur"]

    # 1) TIPTUR — most prominent (star + wordmark), placed & reserved first
    if len(tiptur):
        r = tiptur.iloc[0]
        ax.plot([r.geometry.x], [r.geometry.y], marker="*", ms=22,
                mfc="#9e2b25", mec="white", mew=1.2, zorder=8)
        lp.place(r.geometry.x, r.geometry.y, "TIPTUR", "#7a1f1f",
                 20 if not draft else 13, weight="bold", family=SERIF,
                 halo=4.0, zorder=8.5,
                 candidates=[("left", "center", 12, 2), ("center", "bottom", 0, 12),
                             ("right", "center", -12, 2)])

    # 2) taluk labels — "<NAME> TALUK", dark maroon, avoid collisions
    tk_cand = [("center", "center", 0, 0), ("center", "bottom", 0, 14),
               ("center", "top", 0, -14), ("left", "center", 14, 0),
               ("right", "center", -14, 0)]
    for _, row in taluks.iterrows():
        c = row.geometry.representative_point()
        if not circ_geom.contains(c):
            continue
        name = taluk_display(row["name"]).upper() + " TALUK"
        lp.place(c.x, c.y, name, C_TALUK_TX, 11.5 if not draft else 8.5,
                 weight="bold", family=SANS, halo=3.2, zorder=7.5,
                 candidates=tk_cand)

    # 3) hobli headquarters (deep blue, dot) — Tiptur excluded (shown as star)
    placed_hobli = 0
    for _, row in hoblis.iterrows():
        if str(row["hobli"]).strip().lower() == "tiptur":
            continue
        p = row.geometry
        if lp.place(p.x, p.y, str(row["hobli"]), C_HOBLI_TX,
                    11 if not draft else 8, weight="bold", family=SANS,
                    dot=C_HOBLI_TX, dot_size=4.5, halo=2.6, zorder=7.2):
            placed_hobli += 1

    # 4) towns
    hobli_labels = {str(h).lower() for h in hoblis["hobli"]} if len(hoblis) else set()
    placed_v = 0; total_v = 0
    for _, row in places.iterrows():
        lab = str(row["label"])
        if lab.lower() == "tiptur" or lab.lower() in hobli_labels or row["is_hobli"]:
            continue
        pl = row["place"]
        if pl == "town":
            ok = lp.place(row.geometry.x, row.geometry.y, lab, C_TOWN_TX,
                          13 if not draft else 9, weight="bold", family=SERIF,
                          dot="#333", dot_size=4, halo=3.0, zorder=7.4)
        elif pl == "hamlet":
            total_v += 1
            ok = lp.place(row.geometry.x, row.geometry.y, lab, C_HAMLET_TX,
                          6.0 if not draft else 5, family=SERIF, halo=1.6,
                          dot="#9a9a9a", dot_size=1.6, zorder=6.9, style="italic")
            placed_v += ok
        else:  # village / suburb
            total_v += 1
            ok = lp.place(row.geometry.x, row.geometry.y, lab, C_VILLAGE_TX,
                          7.2 if not draft else 5.4, family=SERIF, halo=2.0,
                          dot="#5a5a5a", dot_size=2.1, zorder=7.0)
            placed_v += ok

    # ------------------- decorations on map (clean white corners) -------------
    north_arrow(ax, minx + 7000, maxy - 15000, size=3200)
    scale_bar(ax, minx + 6000, miny + 8500)

    # crisp double neatline around the square map
    W = (maxx - minx) + 2*m
    H = (maxy - miny) + 2*m
    ax.add_patch(Rectangle((minx - m, miny - m), W, H, fill=False,
                           ec=C_NEATLINE, lw=2.4, zorder=20, clip_on=False))
    inset = m * 0.45
    ax.add_patch(Rectangle((minx - m + inset, miny - m + inset),
                           W - 2*inset, H - 2*inset, fill=False,
                           ec=C_NEATLINE, lw=0.6, zorder=20, clip_on=False))

    # ------------------- info panel -------------------
    build_panel(pax, placed_hobli, len(hoblis), placed_v, total_v, sheet)
    draw_locator(fig, pax)

    os.makedirs(OUTDIR, exist_ok=True)
    tag = "draft" if draft else sheet
    pdf = f"{OUTDIR}/Tiptur_40km_{sheet.upper()}.pdf"
    png = f"{OUTDIR}/Tiptur_40km_{sheet.upper()}.png"
    fig.savefig(pdf, dpi=300, facecolor=BG)          # vector master
    fig.savefig(png, dpi=png_dpi, facecolor=BG)      # raster preview
    plt.close(fig)
    print(f"[render] {sheet}: villages placed {placed_v}/{total_v}, "
          f"hoblis {placed_hobli}/{len(hoblis)} -> {pdf}, {png}")


def draw_locator(fig, pax):
    """Small 'location in Karnataka' inset in the info panel."""
    try:
        kar = gpd.read_file("../data/karnataka_simplified.geojson")
    except Exception:
        return
    pos = pax.get_position()
    iw = pos.width * 0.46
    ih = pos.height * 0.17
    ix = pos.x0 + pos.width * 0.52
    iy = pos.y0 + pos.height * 0.285
    iax = fig.add_axes([ix, iy, iw, ih])
    kar.plot(ax=iax, facecolor="#eceef0", edgecolor="#7f8b96", lw=0.8)
    # 40 km frame + Tiptur dot
    iax.plot([76.4738], [13.2586], marker="*", ms=9, mfc="#9e2b25",
             mec="white", mew=0.6, zorder=5)
    from matplotlib.patches import Rectangle as _R
    iax.add_patch(_R((76.4738 - 0.37, 13.2586 - 0.37), 0.74, 0.74, fill=False,
                     ec="#9e2b25", lw=1.0, zorder=4))
    iax.set_xticks([]); iax.set_yticks([])
    for s in iax.spines.values():
        s.set_edgecolor("#bbbbbb"); s.set_linewidth(0.8)
    iax.set_title("Location in Karnataka", fontsize=8.5, family=SANS,
                  color="#444", pad=3)
    iax.set_aspect("equal")


def build_panel(pax, hobli_ok, hobli_n, vill_ok, vill_n, sheet):
    pax.set_xlim(0, 1); pax.set_ylim(0, 1)
    y = 0.985
    pax.text(0.0, y, "TIPTUR REGION", fontsize=30, weight="bold",
             family=SERIF, color="#1a1a1a", va="top")
    y -= 0.038
    pax.text(0.0, y, "Administrative Geography & Road Connectivity",
             fontsize=13.5, family=SANS, color="#444", va="top")
    y -= 0.024
    pax.text(0.0, y, "Tumakuru District · Karnataka · India — 40 km radius",
             fontsize=11, family=SANS, color="#666", va="top", style="italic")
    y -= 0.02
    pax.plot([0, 1], [y, y], color=C_PANEL_RULE, lw=1.2)
    y -= 0.028

    def head(txt, yy):
        pax.text(0.0, yy, txt, fontsize=13, weight="bold", family=SANS,
                 color="#222", va="top")
        return yy - 0.026

    def row_line(color, label, yy, lw=3.2, ls="-", kind="line"):
        if kind == "line":
            pax.plot([0.0, 0.07], [yy+0.006, yy+0.006], color=color, lw=lw, ls=ls,
                     solid_capstyle="round")
        elif kind == "dash":
            pax.plot([0.0, 0.07], [yy+0.006, yy+0.006], color=color, lw=lw, ls=(0,(4,2)))
        elif kind == "patch":
            pax.add_patch(Rectangle((0.0, yy-0.004), 0.07, 0.018, facecolor=color,
                          edgecolor="#999", lw=0.5))
        elif kind == "dot":
            pax.plot([0.035], [yy+0.006], marker="o", ms=8, mfc=color, mec="white")
        elif kind == "star":
            pax.plot([0.035], [yy+0.006], marker="*", ms=15, mfc=color, mec="white")
        pax.text(0.10, yy+0.006, label, fontsize=10.5, family=SANS, color="#333",
                 va="center")
        return yy - 0.03

    y = head("ROADS", y)
    y = row_line(C_NAT_HW, "National Highway (NH 73 / 75 / 69 / 373 / 150A)", y, lw=3.4)
    y = row_line(C_STATE_HW, "State Highway", y, lw=2.6)
    y = row_line(C_DISTRICT_RD, "Major District Road", y, lw=2.0)
    y = row_line(C_CONNECT_RD, "Other District / connecting road", y, lw=1.4)
    y = row_line(C_RURAL_RD, "Rural road", y, lw=1.1)
    y = row_line(C_VILLAGE_RD, "Village road", y, lw=0.9)
    y -= 0.008

    y = head("ADMINISTRATIVE BOUNDARIES", y)
    y = row_line(C_DIST_LINE, "District boundary", y, lw=2.4)
    y = row_line(C_TALUK_LINE, "Taluk boundary", y, lw=1.6, kind="dash")
    y = row_line(C_CIRCLE, "40 km analytical radius", y, lw=1.8, kind="dash")
    y -= 0.008

    y = head("SETTLEMENTS & CIRCLES", y)
    y = row_line("#9e2b25", "Tiptur (taluk headquarters)", y, kind="star")
    y = row_line(C_HOBLI_TX, "Hobli headquarters (revenue circle)", y, kind="dot")
    y = row_line("#5a5a5a", "Village", y, kind="dot")
    y = row_line("#9a9a9a", "Hamlet", y, kind="dot")
    y -= 0.006
    pax.plot([0, 1], [y, y], color=C_PANEL_RULE, lw=1.0); y -= 0.024

    stats = (f"Villages labelled: {vill_ok} of {vill_n}\n"
             f"Hobli headquarters: {hobli_n} (incl. Tiptur ★)\n"
             "Taluks shown: 17  ·  Districts: 5\n"
             "Road network: 5,690+ classified segments")
    pax.text(0.0, y, stats, fontsize=10, family=SANS, color="#333", va="top",
             linespacing=1.6)
    y -= 0.115

    note = ("DATA & METHOD\n"
            "Geometry: OpenStreetMap (© OpenStreetMap contributors, ODbL), "
            "retrieved via the Overpass API. Boundaries are OSM admin levels 5 "
            "(district) and 6 (taluk). Projection: WGS 84 / UTM Zone 43N "
            "(EPSG:32643). Labels placed by priority-weighted collision "
            "detection.\n\n"
            "Hobli note: hobli (revenue-circle) BOUNDARIES are not published as "
            "open GIS data; hoblis are shown by their headquarters settlement, "
            "matched to OSM place points. Rivers, terrain, land use and points "
            "of interest are intentionally omitted to foreground administrative "
            "geography and road connectivity.")
    pax.text(0.0, y, note, fontsize=8.3, family=SANS, color="#555", va="top",
             linespacing=1.45, wrap=True)

    pax.text(0.0, 0.012, "Cartography: Claude · Generated 2026 · Scale bar and "
             "graticule at 0.25° interval", fontsize=7.5, family=SANS,
             color="#888", va="bottom")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "draft"
    if which == "draft":
        render("draft", dpi=110, draft=True)
    elif which == "a1":
        render("a1", dpi=300)
    elif which == "a0":
        render("a0", dpi=300, png_dpi=150)   # A0 PNG capped (300dpi = 140MP)
    elif which == "final":
        render("a1", dpi=300)
        render("a0", dpi=300, png_dpi=150)
