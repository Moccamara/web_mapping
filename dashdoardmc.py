import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from pathlib import Path
import pandas as pd
import json
import altair as alt
import matplotlib.pyplot as plt
from shapely.geometry import Point

# -----------------------------
# App title
# -----------------------------
st.title("🌍 Geospatial Enterprise Solution")

# ---------------------------------------------------------
# 🔐 PASSWORD AUTHENTICATION
# ---------------------------------------------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

PASSWORD = st.secrets.get("auth", {}).get("dashboard_password", "mocc2025")

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
# Load spatial data
# -----------------------------
DATA_FOLDER = Path("data")
geo_file = next(DATA_FOLDER.glob("*.geojson"), None)
if not geo_file:
    geo_file = next(DATA_FOLDER.glob("*.shp"), None)

if not geo_file:
    st.error("No GeoJSON or Shapefile found.")
    st.stop()

gdf = gpd.read_file(geo_file).to_crs(epsg=4326)
gdf.columns = gdf.columns.str.lower().str.strip()

# Rename fields
gdf = gdf.rename(columns={
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
})

# -----------------------------
# Sidebar filters
# -----------------------------
with st.sidebar:
    st.image("logo/logo_wgv.png", width=180)
    st.markdown("### Administrative Filters")

regions = sorted(gdf["region"].dropna().unique())
region_selected = st.sidebar.selectbox("Region", regions)
gdf_r = gdf[gdf["region"] == region_selected]

cercles = sorted(gdf_r["cercle"].dropna().unique())
cercle_selected = st.sidebar.selectbox("Cercle", cercles)
gdf_c = gdf_r[gdf_r["cercle"] == cercle_selected]

communes = sorted(gdf_c["commune"].dropna().unique())
commune_selected = st.sidebar.selectbox("Commune", communes)
gdf_com = gdf_c[gdf_c["commune"] == commune_selected]

idse_list = ["No filter"] + sorted(gdf_com["idse_new"].dropna().unique())
idse_selected = st.sidebar.selectbox("IDSE_NEW", idse_list)

if idse_selected != "No filter":
    gdf_map = gdf_com[gdf_com["idse_new"] == idse_selected]
else:
    gdf_map = gdf_com.copy()

# Ensure population fields
for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf_map.columns:
        gdf_map[col] = 0

# -----------------------------
# Map center
# -----------------------------
minx, miny, maxx, maxy = gdf_map.total_bounds
center = [(miny + maxy) / 2, (minx + maxx) / 2]

# -----------------------------
# Folium Map
# -----------------------------
m = folium.Map(location=center, zoom_start=17, control_scale=True)

# --- Basemaps ---
folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri",
    name="Satellite",
    overlay=False
).add_to(m)

# --- IDSE layer ---
folium.GeoJson(
    gdf_map,
    name="IDSE Polygons",
    style_function=lambda x: {
        "fillOpacity": 0.15,
        "color": "blue",
        "weight": 2
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new", "pop_se", "pop_se_ct"],
        aliases=["IDSE", "Pop SE", "Pop Actuelle"]
    )
).add_to(m)

# -----------------------------
# CSV points upload
# -----------------------------
st.sidebar.markdown("### CSV Points")
csv_file = st.sidebar.file_uploader("Upload CSV", type="csv")

points_gdf = None
if csv_file:
    df_csv = pd.read_csv(csv_file)
    if {"LAT", "LON"}.issubset(df_csv.columns):
        points_gdf = gpd.GeoDataFrame(
            df_csv,
            geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
            crs="EPSG:4326"
        )

# --- CSV layer ---
if points_gdf is not None:
    fg_points = folium.FeatureGroup(name="CSV Points")
    for _, row in points_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=3,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(fg_points)
    fg_points.add_to(m)

# -----------------------------
# Legend
# -----------------------------
legend_html = """
<div style="
position: fixed;
bottom: 40px; left: 40px;
width: 180px;
background-color: white;
border:2px solid grey;
z-index:9999;
font-size:12px;
padding:10px;">
<b>Legend</b><br>
<hr>
<span style="color:blue;">■</span> IDSE Boundary<br>
<span style="color:red;">●</span> CSV Points
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# --- Layer control ---
folium.LayerControl(collapsed=False).add_to(m)

# -----------------------------
# Layout
# -----------------------------
col_map, col_chart = st.columns([4, 1])

with col_map:
    st.subheader("🗺️ Interactive Map")
    st_folium(m, width=650, height=420)

with col_chart:
    if idse_selected != "No filter":
        df_stat = gdf_map[["idse_new", "pop_se", "pop_se_ct"]]
        df_long = df_stat.melt(
            id_vars="idse_new",
            value_vars=["pop_se", "pop_se_ct"],
            var_name="Type",
            value_name="Population"
        )
        chart = alt.Chart(df_long).mark_bar().encode(
            x="Type:N",
            y="Population:Q",
            color="Type:N"
        ).properties(height=200)
        st.altair_chart(chart, use_container_width=True)

# -----------------------------
# Footer
# -----------------------------
st.markdown("""
---
**Geospatial Web Mapping System**  
Developed with **Streamlit & Python**  
**CAMARA, PhD – Geomatics Engineering © 2025**
""")
