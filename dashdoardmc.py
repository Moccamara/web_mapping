import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
from shapely.geometry import Point
from pathlib import Path
import pandas as pd

# -----------------------------
# App title
# -----------------------------
st.set_page_config(layout="wide")
st.title("🌍 QGIS-Inspired Web GIS – Spatial Query Enabled")

# -----------------------------
# Load spatial data
# -----------------------------
DATA_PATH = Path("data")
geo_file = next(DATA_PATH.glob("*.geojson"), None) or next(DATA_PATH.glob("*.shp"), None)

if not geo_file:
    st.error("No spatial file found in /data")
    st.stop()

gdf = gpd.read_file(geo_file).to_crs(epsg=4326)
gdf.columns = gdf.columns.str.lower().str.strip()

rename_map = {
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
}
gdf = gdf.rename(columns=rename_map)

# -----------------------------
# Sidebar + LOGO
# -----------------------------
with st.sidebar:
    st.image("logo/logo_wgv.png", width=200)
    st.markdown("### Geographical level")

# -----------------------------
# Sidebar filters (Attribute Query)
# -----------------------------
st.sidebar.header("🗂️ Attribute Query")

regions = sorted(gdf["region"].dropna().unique())
region = st.sidebar.selectbox("Region", regions)

gdf_r = gdf[gdf["region"] == region]
cercles = sorted(gdf_r["cercle"].dropna().unique())
cercle = st.sidebar.selectbox("Cercle", cercles)

gdf_c = gdf_r[gdf_r["cercle"] == cercle]
communes = sorted(gdf_c["commune"].dropna().unique())
commune = st.sidebar.selectbox("Commune", communes)

gdf_f = gdf_c[gdf_c["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].dropna().unique().tolist())
idse_selected = st.sidebar.selectbox("IDSE_NEW (optionnal)", idse_list)

# Filter GeoJSON by IDSE_NEW
gdf_idse = gdf_commune.copy()
if idse_selected != "No filtre":
    gdf_idse = gdf_commune[gdf_commune["idse_new"] == idse_selected]

# Create missing pop columns if needed
for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf_idse.columns:
        gdf_idse[col] = 0

# -----------------------------
# Map center
# -----------------------------
minx, miny, maxx, maxy = gdf_f.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# -----------------------------
# Create Folium Map
# -----------------------------
m = folium.Map(location=[center_lat, center_lon], zoom_start=5)

# -----------------------------
# Basemaps
# -----------------------------
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Satellite (Esri)",
    overlay=False
).add_to(m)

# -----------------------------
# Polygon layer
# -----------------------------
folium.GeoJson(
    gdf_f,
    name="IDSE Polygons",
    style_function=lambda x: {
        "color": "blue",
        "weight": 2,
        "fillOpacity": 0.1
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new", "commune"],
        aliases=["IDSE", "Commune"]
    )
).add_to(m)

# -----------------------------
# Measure tool
# -----------------------------
MeasureControl(
    position="topright",
    primary_length_unit="meters",
    primary_area_unit="sqmeters"
).add_to(m)

# -----------------------------
# Digitize / Draw tool
# -----------------------------
Draw(
    position="topright",
    export=True,
    filename="digitized.geojson",
    draw_options={
        "polyline": True,
        "polygon": True,
        "rectangle": True,
        "marker": True,
        "circle": False
    }
).add_to(m)

# -----------------------------
# Layer control (collapsed)
# -----------------------------
folium.LayerControl(collapsed=True).add_to(m)

# -----------------------------
# Collapsible legend
# -----------------------------
legend_html = """
<div style="position: fixed; bottom: 40px; left: 40px; z-index:9999;">
<details>
<summary style="background:white;padding:6px;border:2px solid grey;cursor:pointer;">
Legend
</summary>
<div style="background:white;padding:10px;border:2px solid grey;width:180px;">
<span style="color:blue;">■</span> IDSE Polygon<br>
📏 Measure Tool<br>
✏️ Digitize Tool<br>
🖱️ Click = Spatial Query
</div>
</details>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# -----------------------------
# Display map
# -----------------------------
st.subheader("🗺️ Click on the map to run a spatial query")
map_data = st_folium(m, height=520, width=1000)

# -----------------------------
# SPATIAL QUERY (Map Click)
# -----------------------------
st.subheader("📍 Spatial Query Result")

if map_data and map_data.get("last_clicked"):
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

    clicked_point = Point(lon, lat)
    gdf_point = gpd.GeoDataFrame(geometry=[clicked_point], crs="EPSG:4326")

    intersected = gpd.sjoin(gdf_point, gdf_f, predicate="within")

    if not intersected.empty:
        row = intersected.iloc[0]
        st.success("IDSE Found ✔")
        st.write({
            "IDSE": row["idse_new"],
            "Commune": row["commune"],
            "Cercle": row["cercle"],
            "Region": row["region"]
        })
    else:
        st.warning("No IDSE polygon at this location")

else:
    st.info("Click anywhere on the map to identify spatial features")

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
**Project:** QGIS-Inspired Web GIS with Spatial Query  
Developed using Streamlit, Folium & GeoPandas  
**CAMARA, PhD – Geomatics Engineering** © 2025
""")


