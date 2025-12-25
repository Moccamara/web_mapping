import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
from pathlib import Path
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import requests

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
# SESSION STATE INITIALIZATION
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.user_role = None
    st.session_state.username = None
    st.session_state.login_attempted = False

# =========================================================
# LOGIN SIDEBAR
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    login_btn = st.sidebar.button("Login")
    if login_btn:
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.auth_ok = True
            st.session_state.user_role = USERS[username]["role"]
            st.session_state.username = username
            st.success(f"Logged in as {username} ({st.session_state.user_role})")
        else:
            st.error("❌ Invalid username or password")
    st.stop()
else:
    st.sidebar.success(f"Logged in as {st.session_state.username} ({st.session_state.user_role})")

# =========================================================
# LOAD SE POLYGONS FROM GITHUB (RAW)
# =========================================================
SE_URL = "https://raw.githubusercontent.com/Moccamara/web_mapping/master/data/SE.geojson"

@st.cache_data(show_spinner=False)
def load_se_data(url):
    gdf = gpd.read_file(url)

    # CRS
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    # Normalize columns
    gdf.columns = gdf.columns.str.lower().str.strip()

    # Rename fields
    gdf = gdf.rename(columns={
        "lregion": "region",
        "lcercle": "cercle",
        "lcommune": "commune"
    })

    # Geometry cleaning
    gdf = gdf[gdf.is_valid & ~gdf.is_empty]

    # Required fields
    for col in ["region", "cercle", "commune", "idse_new"]:
        if col not in gdf.columns:
            gdf[col] = ""

    for col in ["pop_se", "pop_se_ct"]:
        if col not in gdf.columns:
            gdf[col] = 0

    return gdf

# 🔴 THIS LINE WAS MISSING
try:
    gdf = load_se_data(SE_URL)
except Exception:
    st.error("❌ Unable to load SE.geojson from GitHub")
    st.stop()

# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.image("logo/logo_wgv.png", use_container_width=True)
st.sidebar.markdown("### 🗂️ Attribute Query")

region = st.sidebar.selectbox("Region", sorted(gdf["region"].dropna().unique()))
gdf_r = gdf[gdf["region"] == region]

cercle = st.sidebar.selectbox("Cercle", sorted(gdf_r["cercle"].dropna().unique()))
gdf_c = gdf_r[gdf_r["cercle"] == cercle]

commune = st.sidebar.selectbox("Commune", sorted(gdf_c["commune"].dropna().unique()))
gdf_commune = gdf_c[gdf_c["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].dropna().unique())
idse_selected = st.sidebar.selectbox("Unit_Geo", idse_list)
gdf_idse = gdf_commune if idse_selected == "No filtre" else gdf_commune[gdf_commune["idse_new"] == idse_selected]

# =========================================================
# CSV UPLOAD (POINTS) - Admin only
# =========================================================
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
import os

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Shared Points Map", layout="wide")

DATA_DIR = "data"
GEOJSON_PATH = os.path.join(DATA_DIR, "shared_points.geojson")

os.makedirs(DATA_DIR, exist_ok=True)

# =========================================================
# SIMULATED AUTH (replace with your real auth system)
# =========================================================
if "user_role" not in st.session_state:
    st.session_state.user_role = "Customer"  # default

st.sidebar.markdown("### 👤 User Role")
role = st.sidebar.radio(
    "Select role (demo)",
    ["Admin", "Customer"],
    index=0 if st.session_state.user_role == "Admin" else 1
)
st.session_state.user_role = role

# =========================================================
# ADMIN: CSV UPLOAD
# =========================================================
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Upload CSV (Admin only)")
    csv_file = st.sidebar.file_uploader(
        "Upload CSV file",
        type=["csv"]
    )

    if csv_file:
        df = pd.read_csv(csv_file)

        if {"LAT", "LON"}.issubset(df.columns):
            df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
            df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
            df = df.dropna(subset=["LAT", "LON"])

            gdf = gpd.GeoDataFrame(
                df,
                geometry=gpd.points_from_xy(df["LON"], df["LAT"]),
                crs="EPSG:4326"
            )

            gdf.to_file(GEOJSON_PATH, driver="GeoJSON")
            st.sidebar.success("✅ Points uploaded and shared successfully")

        else:
            st.sidebar.error("❌ CSV must contain LAT and LON columns")

# =========================================================
# LOAD SHARED POINTS (ALL USERS)
# =========================================================
points_gdf = None
if os.path.exists(GEOJSON_PATH):
    points_gdf = gpd.read_file(GEOJSON_PATH)

# =========================================================
# MAP DISPLAY
# =========================================================
st.title("📍 Shared Points Map")

m = folium.Map(location=[0, 0], zoom_start=2, control_scale=True)

if points_gdf is not None and not points_gdf.empty:
    for _, row in points_gdf.iterrows():
        popup_text = "<br>".join(
            [f"<b>{col}</b>: {row[col]}" for col in points_gdf.columns if col != "geometry"]
        )

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=popup_text,
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    # Zoom to points
    m.fit_bounds([
        [points_gdf.geometry.y.min(), points_gdf.geometry.x.min()],
        [points_gdf.geometry.y.max(), points_gdf.geometry.x.max()]
    ])
else:
    st.info("No points available yet. Admin must upload a CSV.")

st_folium(m, width=1100, height=600)


# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=19)

folium.TileLayer("OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    name="Satellite",
    attr="Esri"
).add_to(m)
m.fit_bounds([[miny, minx], [maxy, maxx]])
folium.GeoJson(
    gdf_idse,
    name="IDSE",
    style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.15},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"])
).add_to(m)
if points_gdf is not None:
    for _, r in points_gdf.iterrows():
        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=3,
            color="red",
            fill=True,
            fill_opacity=0.8
        ).add_to(m)
MeasureControl().add_to(m)
Draw(export=True).add_to(m)
folium.LayerControl(collapsed=True).add_to(m)

# =========================================================
# LAYOUT
# =========================================================
col_map, col_chart = st.columns((3, 1), gap="small")
with col_map:
    st_folium(m, height=450, use_container_width=True)
with col_chart:
    if idse_selected == "No filtre":
        st.info("Select SE.")
    else:
        # ===============================
        # Population bar chart
        # ===============================
        st.subheader("📊 Population")
        df_long = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].copy()
        df_long["idse_new"] = df_long["idse_new"].astype(str)
        df_long = df_long.melt(
            id_vars="idse_new",
            value_vars=["pop_se", "pop_se_ct"],
            var_name="Variable",
            value_name="Population"
        )
        df_long["Variable"] = df_long["Variable"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })
        chart = (
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x=alt.X("idse_new:N", title=None),
                xOffset="Variable:N",
                y=alt.Y("Population:Q", title=None),
                color=alt.Color(
                    "Variable:N",
                    legend=alt.Legend(orient="right", title="Type")
                ),
                tooltip=["idse_new", "Variable", "Population"]
            )
            .properties(height=130)
        )
        st.altair_chart(chart, use_container_width=True)

        # ===============================
        # Sex pie chart (SAFE)
        # ===============================
        st.subheader("👥 Sex (M / F)")
        try:
            if (
                points_gdf is not None
                and {"Masculin", "Feminin"}.issubset(points_gdf.columns)
            ):
                pts = gpd.sjoin(points_gdf, gdf_idse, predicate="within")

                if not pts.empty:
                    values = [
                        pts["Masculin"].sum(),
                        pts["Feminin"].sum()
                    ]
                    if sum(values) > 0:
                        fig, ax = plt.subplots(figsize=(1, 1))
                        ax.pie(
                            values,
                            labels=["M", "F"],
                            autopct="%1.1f%%",
                            textprops={
                                "fontsize": 5,
                            }
                        )
                        st.pyplot(fig)
        except Exception:
            pass  # 🔇 no Streamlit error message


# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping** Developed with Streamlit, Folium & GeoPandas  
**Mahamadou CAMARA, PhD – Geomatics Engineering** © 2025
""")
























