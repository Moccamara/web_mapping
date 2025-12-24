import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import json

# -----------------------------
# App title
# -----------------------------
st.title("🌍 Geospatial Enterprise Solution")

# -----------------------------
# Authentication
# -----------------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

PASSWORD = "mocc2025"

if not st.session_state.auth_ok:
    with st.sidebar:
        st.header("🔐 Login")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == PASSWORD:
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("Incorrect password")
    st.stop()

# -----------------------------
# Load GeoData
# -----------------------------
DATA_PATH = Path("data")
geo_file = next(DATA_PATH.glob("*.geojson"), None) or next(DATA_PATH.glob("*.shp"), None)

if not geo_file:
    st.error("No GeoJSON or Shapefile found.")
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
# Sidebar Filters
# -----------------------------
with st.sidebar:
    st.image("logo/logo_wgv.png", width=200)
    st.markdown("### Administrative Filters")

regions = sorted(gdf["region"].dropna().unique())
region = st.sidebar.selectbox("Region", regions)

gdf_r = gdf[gdf["region"] == region]
cercles = sorted(gdf_r["cercle"].dropna().unique())
cercle = st.sidebar.selectbox("Cercle", cercles)

gdf_c = gdf_r[gdf_r["cercle"] == cercle]
communes = sorted(gdf_c["commune"].dropna().unique())
commune = st.sidebar.selectbox("Commune", communes)

gdf_com = gdf_c[gdf_c["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_com["idse_new"].dropna().unique())
idse = st.sidebar.selectbox("IDSE_NEW", idse_list)

if idse != "No filtre":
    gdf_com = gdf_com[gdf_com["idse_new"] == idse]

# -----------------------------
# Map center
# -----------------------------
minx, miny, maxx, maxy = gdf_com.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# -----------------------------
# Folium Map
# -----------------------------
m = folium.Map(location=[center_lat, center_lon], zoom_start=18)

# --- Basemaps (hidden by default) ---
folium.TileLayer(
    "OpenStreetMap",
    name="OpenStreetMap",
    control=True
).add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Satellite (Esri)",
    overlay=False,
    control=True
).add_to(m)

# -----------------------------
# IDSE Polygon Layer
# -----------------------------
folium.GeoJson(
    gdf_com,
    name="IDSE Polygons",
    style_function=lambda x: {
        "color": "blue",
        "weight": 2,
        "fillOpacity": 0.1
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new"],
        aliases=["IDSE"]
    )
).add_to(m)

# -----------------------------
# Upload CSV Points
# -----------------------------
st.sidebar.markdown("### Upload CSV Points")
csv_file = st.sidebar.file_uploader("CSV with LAT, LON", type=["csv"])

if csv_file:
    df_csv = pd.read_csv(csv_file)
    points_layer = folium.FeatureGroup(name="CSV Points")

    for _, r in df_csv.iterrows():
        folium.CircleMarker(
            location=[r["LAT"], r["LON"]],
            radius=3,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(points_layer)

    points_layer.add_to(m)

# -----------------------------
# Layer Control (collapsed)
# -----------------------------
folium.LayerControl(collapsed=True).add_to(m)

# -----------------------------
# Collapsible Legend
# -----------------------------
legend_html = """
<div style="position: fixed; bottom: 40px; left: 40px; z-index:9999;">
<details>
<summary style="background:white;padding:6px;border:2px solid grey;cursor:pointer;">
Legend
</summary>
<div style="background:white;padding:10px;border:2px solid grey;width:180px;">
<span style="color:blue;">■</span> IDSE Boundary<br>
<span style="color:red;">●</span> CSV Points
</div>
</details>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# -----------------------------
# Display Map
# -----------------------------
st.subheader(f"🗺️ {commune}")
st_folium(m, width=700, height=450)

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
**Project:** Geospatial Web Mapping  
Developed with Streamlit & Python by **CAMARA, PhD** © 2025
""")
