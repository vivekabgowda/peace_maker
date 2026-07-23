# Tiptur Region — Publication Map (40 km radius)

A museum-quality, print-ready cartographic map of **every village within a 40 km
radius of Tiptur, Tumakuru District, Karnataka, India**, focused on
administrative geography and road connectivity. Built entirely from open GIS
data with a reproducible Python pipeline.

![Tiptur 40 km map](output/Tiptur_40km_A0.png)

---

## Deliverables

### Print files — `output/`
| File | Format | Use |
|------|--------|-----|
| `Tiptur_40km_A0.pdf` | Vector, A0 landscape (1189 × 841 mm) | **Master for offset / large-format printing** |
| `Tiptur_40km_A1.pdf` | Vector, A1 landscape (841 × 594 mm) | Master for A1 printing |
| `Tiptur_40km_A0.png` | Raster, 150 dpi | Preview / screen |
| `Tiptur_40km_A1.png` | Raster, 300 dpi | High-res raster deliverable |

PDFs are fully vector (text and linework stay crisp at any print size).

### Editable GIS project — `gis/`
| Item | Description |
|------|-------------|
| `tiptur_gis.gpkg` | GeoPackage, **EPSG:32643 (UTM 43N)**, all layers, with **embedded QGIS styles** (auto-applied on open) |
| `tiptur_map.qgs` | QGIS project referencing the GeoPackage |
| `geojson/*.geojson` | Every layer in WGS84 (portable; opens in ArcGIS Pro / web GIS) |
| `qml/*.qml` | QGIS layer styles (load manually if needed) |

**Layers:** `roads_classified` (by class), `districts`, `taluks`,
`hobli_headquarters`, `places` (villages/hamlets/towns), `circle_40km`, `frame`.

**To open in QGIS:** either open `tiptur_map.qgs`, or simply drag
`tiptur_gis.gpkg` into QGIS — the embedded styles apply automatically.

---

## What the map shows

* **All villages** within 40 km — 971 place points (893 villages, 88 hamlets,
  5 towns), individually labelled (967 labelled on the A0 sheet by
  priority-weighted collision detection).
* **Hobli headquarters** — 19 revenue-circle centres (incl. Tiptur), deep-blue.
* **Taluk boundaries** — 17 taluks (OSM admin level 6), dark-grey dashed, labelled.
* **District boundaries** — 5 districts (OSM admin level 5), near-black.
* **Full classified road network** — 5,694 segments, real GIS geometry:
  * National Highways (NH 73 / 75 / 69 / 373 / 150A) — dark red
  * State Highways — muted orange
  * Major District Roads — medium grey
  * Other district / connecting, rural, and village roads — graded greys
* **40 km analytical radius** — thin dashed blue circle (true circle in UTM).
* Karnataka **locator inset**, north arrow, scale bar, 0.2° graticule, legend.

Deliberately **excluded** (per brief): rivers, lakes, streams, forests,
terrain, hill-shading, railways, bus stands, markets, POIs, satellite imagery.

---

## Data sources

* **OpenStreetMap** © OpenStreetMap contributors, **ODbL** — roads, place points,
  and administrative boundaries (admin levels 5 & 6), retrieved live via the
  **Overpass API**.
* **geoBoundaries** (CGAZ) — Karnataka state outline for the locator inset only.
* Tiptur centre geocoded via **Nominatim** (13.25858 °N, 76.47377 °E).

### Note on Hoblis (important, honest limitation)
Hobli (revenue-circle) **boundaries are not published as open GIS data** and do
not exist in OpenStreetMap (there are no admin-level-7 boundaries in this
region). Hoblis are therefore shown by their **headquarters settlement** — real
OSM place points, matched from an authoritative hobli list per taluk (the Gubbi
set cross-checked against Wikipedia). **No hobli boundaries or coordinates were
fabricated;** any hobli HQ that could not be matched to a real OSM point was
dropped, not invented.

---

## Reproduce

```bash
pip install -r requirements.txt          # geopandas, osmnx, shapely, matplotlib …
cd scripts
python overpass.py        # (optional) probe admin-level structure
python fetch_data.py all  # pull roads / boundaries / places from Overpass
python process.py         # project (UTM 43N), dissolve, classify, clip, match hoblis
python render.py final    # render A0 + A1 (PDF + PNG)
python export_gis.py      # build GeoPackage + GeoJSON + QML + QGIS project
```

`render.py draft` produces a fast low-res proof.

## Pipeline
```
overpass.py    robust Overpass client (endpoint rotation + backoff)
fetch_data.py  OSM → data/tiptur_raw.gpkg  (boundaries_l5/l6, roads, places)
fetch_hoblis.py  Wikipedia hobli-name extraction (audit aid)
process.py     → data/tiptur_processed.gpkg (EPSG:32643, classified, clipped)
render.py      → output/  A0 & A1 PDF + PNG
export_gis.py  → gis/     GeoPackage (+embedded styles), GeoJSON, QML, .qgs
```

## Projection & scale
* CRS: **WGS 84 / UTM Zone 43N (EPSG:32643)** — minimal distortion at ~76.5 °E;
  the 40 km radius renders as a true circle.
* Approx. scale on A0: **1 : 165,000**.

## Licence
Derived from OpenStreetMap data — © OpenStreetMap contributors, released under
the **Open Database License (ODbL)**. Any redistribution of the map or data must
retain this attribution.
