"""Assemble the editable GIS deliverable:

  gis/tiptur_gis.gpkg      – clean, well-named layers (EPSG:32643) + embedded
                             QGIS styles (auto-applied on open)
  gis/geojson/*.geojson    – each layer in WGS84 (portable, ArcGIS/web ready)
  gis/qml/*.qml            – QGIS layer styles (load manually if desired)
  gis/tiptur_map.qgs       – QGIS project referencing the GeoPackage
"""
import os
import sqlite3
import shutil
import geopandas as gpd

SRC = "../data/tiptur_processed.gpkg"
GIS = "../gis"
GPKG = f"{GIS}/tiptur_gis.gpkg"
UTM = 32643

# processed layer -> clean deliverable name
LAYER_MAP = {
    "circle40": "circle_40km",
    "frame": "frame",
    "districts": "districts",
    "taluks": "taluks",
    "roads": "roads_classified",
    "places": "places",
    "hoblis": "hobli_headquarters",
}

# ------------------------------- QML styles ---------------------------------
def line_sym(color, width, dash=None):
    dash_props = (f'<Option value="{dash}" name="customdash" type="QString"/>'
                  '<Option value="1" name="use_custom_dash" type="QString"/>') if dash else ''
    return f'''<layer class="SimpleLine" pass="0" enabled="1">
      <Option type="Map">
        <Option value="{color}" name="line_color" type="QString"/>
        <Option value="{width}" name="line_width" type="QString"/>
        <Option value="MM" name="line_width_unit" type="QString"/>
        <Option value="round" name="capstyle" type="QString"/>
        <Option value="round" name="joinstyle" type="QString"/>
        {dash_props}
      </Option>
    </layer>'''


def roads_qml():
    cats = [
        ("national_highway", "#9e2b25", 0.9, "National Highway"),
        ("state_highway",   "#e08a1e", 0.7, "State Highway"),
        ("district_road",   "#8f8f8f", 0.5, "Major District Road"),
        ("connecting_road", "#b4b4b4", 0.35, "Other District / connecting"),
        ("rural_road",      "#cfcfcf", 0.25, "Rural road"),
        ("village_road",    "#e2e2e2", 0.2, "Village road"),
    ]
    cat_xml, sym_xml = [], []
    for i, (val, col, w, lbl) in enumerate(cats):
        cat_xml.append(f'<category render="true" value="{val}" symbol="{i}" label="{lbl}"/>')
        sym_xml.append(f'<symbol name="{i}" type="line" alpha="1">{line_sym(col, w)}</symbol>')
    return f'''<!DOCTYPE qgis><qgis version="3.34" styleCategories="Symbology|Labeling">
  <renderer-v2 type="categorizedSymbol" attr="cls">
    <categories>{''.join(cat_xml)}</categories>
    <symbols>{''.join(sym_xml)}</symbols>
  </renderer-v2>
</qgis>'''


def simple_line_qml(color, width, dash=None):
    return f'''<!DOCTYPE qgis><qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="singleSymbol">
    <symbols><symbol name="0" type="line" alpha="1">{line_sym(color, width, dash)}</symbol></symbols>
  </renderer-v2></qgis>'''


def fill_qml(fill, outline, owidth, dash=None):
    dash_props = (f'<Option value="{dash}" name="customdash" type="QString"/>'
                  '<Option value="1" name="use_custom_dash" type="QString"/>') if dash else ''
    return f'''<!DOCTYPE qgis><qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="singleSymbol"><symbols>
   <symbol name="0" type="fill" alpha="1">
    <layer class="SimpleFill" enabled="1">
     <Option type="Map">
      <Option value="{fill}" name="color" type="QString"/>
      <Option value="{outline}" name="outline_color" type="QString"/>
      <Option value="{owidth}" name="outline_width" type="QString"/>
      <Option value="MM" name="outline_width_unit" type="QString"/>
      {dash_props}
     </Option>
    </layer></symbol></symbols></renderer-v2></qgis>'''


def point_qml(color, size, label_field, label_color, label_size, bold="0"):
    return f'''<!DOCTYPE qgis><qgis version="3.34" styleCategories="Symbology|Labeling">
  <renderer-v2 type="singleSymbol"><symbols>
   <symbol name="0" type="marker" alpha="1">
    <layer class="SimpleMarker" enabled="1">
     <Option type="Map">
      <Option value="{color}" name="color" type="QString"/>
      <Option value="circle" name="name" type="QString"/>
      <Option value="{size}" name="size" type="QString"/>
      <Option value="white" name="outline_color" type="QString"/>
      <Option value="0.2" name="outline_width" type="QString"/>
     </Option>
    </layer></symbol></symbols></renderer-v2>
  <labeling type="simple">
   <settings>
    <text-style fieldName="{label_field}" fontSize="{label_size}"
       fontFamily="Sans" fontBold="{bold}" textColor="{label_color}">
     <text-buffer bufferDraw="1" bufferSize="0.8" bufferColor="255,255,255,255"/>
    </text-style>
    <placement placement="1" dist="1"/>
   </settings>
  </labeling></qgis>'''


STYLES = {
    "roads_classified": roads_qml(),
    "districts": simple_line_qml("#2b2b2b", 0.6),
    "taluks": fill_qml("#f2efe9", "#4d4d4d", 0.3, dash="4;2"),
    "circle_40km": simple_line_qml("#3b6ea5", 0.5, dash="7;4"),
    "places": point_qml("#5a5a5a", 1.4, "label", "#2b2b2b", 7),
    "hobli_headquarters": point_qml("#1f3f73", 2.6, "hobli", "#1f3f73", 10, bold="1"),
    "frame": simple_line_qml("#222222", 0.4),
}


def embed_styles(gpkg):
    con = sqlite3.connect(gpkg)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS layer_styles(
        id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT,
        f_table_schema TEXT, f_table_name TEXT, f_geometry_column TEXT,
        styleName TEXT, styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN,
        description TEXT, owner TEXT, ui TEXT, update_time DATETIME
        DEFAULT (datetime('now')))""")
    for layer, qml in STYLES.items():
        cur.execute("DELETE FROM layer_styles WHERE f_table_name=?", (layer,))
        cur.execute("""INSERT INTO layer_styles(f_table_catalog,f_table_schema,
            f_table_name,f_geometry_column,styleName,styleQML,styleSLD,
            useAsDefault,description,owner)
            VALUES('','',?,?,?,?,'',1,?, 'tiptur-map')""",
            (layer, "geom", layer, qml, f"default style for {layer}"))
    con.commit(); con.close()


def _inner(qml):
    """Strip the <qgis> wrapper, returning inner renderer/labeling XML."""
    s = qml.split(">", 1)[1]           # drop <!DOCTYPE qgis>
    s = s.split(">", 1)[1]             # drop <qgis ...>
    return s.rsplit("</qgis>", 1)[0]


SRS_32643 = '''<spatialrefsys>
  <wkt>PROJCRS["WGS 84 / UTM zone 43N"]</wkt>
  <proj4>+proj=utm +zone=43 +datum=WGS84 +units=m +no_defs</proj4>
  <srid>32643</srid><authid>EPSG:32643</authid>
  <description>WGS 84 / UTM zone 43N</description>
  <projectionacronym>utm</projectionacronym>
  <ellipsoidacronym>EPSG:7030</ellipsoidacronym><geographicflag>false</geographicflag>
</spatialrefsys>'''

GEOM_TYPE = {
    "circle_40km": "Polygon", "frame": "Polygon", "districts": "Polygon",
    "taluks": "Polygon", "roads_classified": "Line", "places": "Point",
    "hobli_headquarters": "Point",
}
# draw order bottom -> top
DRAW_ORDER = ["frame", "taluks", "circle_40km", "roads_classified",
              "districts", "places", "hobli_headquarters"]


def write_qgs():
    layers_xml, tree_xml, order_xml = [], [], []
    for name in DRAW_ORDER:
        lid = f"{name}_lyr"
        style = _inner(STYLES[name]) if name in STYLES else ""
        layers_xml.append(f'''<maplayer type="vector" geometry="{GEOM_TYPE[name]}">
    <id>{lid}</id>
    <datasource>./tiptur_gis.gpkg|layername={name}</datasource>
    <layername>{name}</layername>
    <provider>ogr</provider>
    <srs>{SRS_32643}</srs>
    {style}
  </maplayer>''')
        tree_xml.append(f'<layer-tree-layer id="{lid}" name="{name}" '
                        f'source="./tiptur_gis.gpkg|layername={name}" '
                        f'providerKey="ogr" checked="Qt::Checked"/>')
        order_xml.append(f'<item>{lid}</item>')
    qgs = f'''<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" projectname="Tiptur 40 km Administrative &amp; Road Map">
  <projectCrs>{SRS_32643}</projectCrs>
  <layer-tree-group>
    {''.join(reversed(tree_xml))}
  </layer-tree-group>
  <layerorder>{''.join(reversed(order_xml))}</layerorder>
  <projectlayers>
    {''.join(layers_xml)}
  </projectlayers>
</qgis>'''
    with open(f"{GIS}/tiptur_map.qgs", "w") as f:
        f.write(qgs)
    print(f"[export] QGIS project -> {GIS}/tiptur_map.qgs")


def main():
    os.makedirs(GIS, exist_ok=True)
    os.makedirs(f"{GIS}/geojson", exist_ok=True)
    os.makedirs(f"{GIS}/qml", exist_ok=True)
    if os.path.exists(GPKG):
        os.remove(GPKG)

    for src_layer, name in LAYER_MAP.items():
        try:
            g = gpd.read_file(SRC, layer=src_layer)
        except Exception:
            continue
        g = g.set_geometry("geometry")
        g.to_file(GPKG, layer=name, driver="GPKG")
        g.to_crs(4326).to_file(f"{GIS}/geojson/{name}.geojson", driver="GeoJSON")
        if name in STYLES:
            with open(f"{GIS}/qml/{name}.qml", "w") as f:
                f.write(STYLES[name])
        print(f"  exported {name}: {len(g)} features")

    embed_styles(GPKG)
    print(f"[export] GeoPackage + styles -> {GPKG}")
    write_qgs()

    # copy Karnataka locator for completeness
    if os.path.exists("../data/karnataka_simplified.geojson"):
        shutil.copy("../data/karnataka_simplified.geojson",
                    f"{GIS}/geojson/karnataka_state.geojson")


if __name__ == "__main__":
    main()
