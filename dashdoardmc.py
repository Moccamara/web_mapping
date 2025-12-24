import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
from pathlib import Path
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(layout="wide", page_title="Geospatial Enterprise Solution")
st.title("🌍 Geospatial Enterprise Solution")

# =========================================================
# USERS AND ROLES
# =========================================================
USERS = {
    "admin": {"password": "admin2025", "role": "Admin"},
    "customer": {"password": "cust2025", "role": "Customer"}
}

# =========================================================
# SESSION STATE INIT
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.user_role = None
    st.session_state.username = None

# =========================================================
# LOGIN SIDEBAR
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.auth_ok = True
            st.session_state.user_role = USERS[username]["role"]
            st.session_state.username = username
            st.success(f"Logged in as {username}")
        else:
            st.error("Invalid credentials")
    st.stop()
else:
    st.sidebar.success(f"{st.session_state.username} ({st.session_state.user_role})")

# =========================================================
# PATHS
# =========================================================
DATA_PATH = Path("data")
DATA_PATH.mkdir(exist_ok=True)

SE_FILE = DATA_PATH / "se.geojson"
POINTS_FILE = DATA_PATH / "concession.geojson"

# =========================================================
# LOAD SE POLYGONS (MAIN DATA)
# =========================================================
if not SE_FILE.exists():
    st.error("❌ se.geojson not found in /data")
    st.stop()

gdf = gpd.read_file(SE_FILE).to_crs(epsg=4326)

# Normalize column names
gdf.columns = gdf.columns.str.lower().str.strip()

# Rename if needed
gdf = gdf.rename(columns={
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune"
})

# Ensure required columns
for col in ["region", "cercle", "commune", "idse_new"]:
    if col not in gdf.columns:
        gdf[col] = ""

for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf.columns:
        gdf[col] = 0

gdf = gdf[gdf.is_valid & ~gdf.is_empty]

# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.image("logo/logo_wgv.png", use_container_width=True)
st.sidebar.markdown("### 🗂️ Attribute Query")

region = st.sidebar.selectbox("Region", sorted(gdf["region"].unique()))
gdf_r = gdf[gdf["region"] == region]

cercle = st.sidebar.selectbox("Cercle", sorted(gdf_r["cercle"].unique()))
gdf_c = gdf_r[gdf_r["cercle"] == cercle]

commune = st.sidebar.selectbox("Commune", sorted(gdf_c["commune"].unique()))
gdf_commune = gdf_c[gdf_c["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].unique())
idse_selected = st.sidebar.selectbox("IDSE_NEW", idse_list)

gdf_idse = gdf_commune if idse_selected == "No filtre" else gdf_commune[gdf_commune["idse_new"] == idse_selected]

# =========================================================
# POINTS UPLOAD & AUTO GEOJSON
# =========================================================
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Import CSV Points")
    csv_file = st.sidebar.file_uploader("Upload CSV", type="csv")

    if csv_file:
        df_csv = pd.read_csv(csv_file)
        if {"LAT", "LON"}.issubset(df_csv.columns):
            df_csv = df_csv.dropna(subset=["LAT", "LON"])
            points_gdf = gpd.GeoDataFrame(
                df_csv,
                geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
                crs="EPSG:4326"
            )
            points_gdf.to_file(POINTS_FILE, driver="GeoJSON")
            st.sidebar.success("Concession points saved")
        else:
            st.sidebar.error("CSV must contain LAT and LON")

# Load points for all users
points_gdf = gpd.read_file(POINTS_FILE) if POINTS_FILE.exists() else None

# =========================================================
# MAP
# =========================================================
if not gdf_idse.empty:
    minx, miny, maxx, maxy = gdf_idse.total_bounds
    center = [(miny + maxy) / 2, (minx + maxx) / 2]
else:
    center = [13.5, -7.9]

m = folium.Map(location=center, zoom_start=14)

folium.TileLayer("OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    name="Satellite",
    attr="Esri"
).add_to(m)

if not gdf_idse.empty:
    m.fit_bounds([[miny, minx], [maxy, maxx]])

folium.GeoJson(
    gdf_idse,
    name="SE",
    style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.15},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"])
).add_to(m)

if points_gdf is not None:
    for _, r in points_gdf.iterrows():
        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(m)

MeasureControl().add_to(m)
Draw(export=True).add_to(m)
folium.LayerControl().add_to(m)

# =========================================================
# DISPLAY
# =========================================================
st_folium(m, height=500, use_container_width=True)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping**  
**CAMARA, PhD – Geomatics Engineering** © 2025
""")
