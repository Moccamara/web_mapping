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
# LOAD SPATIAL DATA
# =========================================================
DATA_PATH = Path("data")
geo_file = next(DATA_PATH.glob("*.geojson"), None) or next(DATA_PATH.glob("*.shp"), None)
if not geo_file:
    st.error("No GeoJSON or Shapefile found in /data")
    st.stop()

gdf = gpd.read_file(geo_file).to_crs(epsg=4326)
gdf.columns = gdf.columns.str.lower().str.strip()
gdf = gdf.rename(columns={
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
})
gdf = gdf[gdf.is_valid & ~gdf.is_empty]

for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf.columns:
        gdf[col] = 0

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
idse_selected = st.sidebar.selectbox("IDSE_NEW", idse_list)
gdf_idse = gdf_commune if idse_selected == "No filtre" else gdf_commune[gdf_commune["idse_new"] == idse_selected]

# =========================================================
# POINTS UPLOAD & AUTOMATIC GEOJSON
# =========================================================
# =========================================================
# POINTS UPLOAD & AUTOMATIC GEOJSON
# =========================================================
DATA_PATH = Path("data")
DATA_PATH.mkdir(exist_ok=True)

points_csv_path = DATA_PATH / "concession.csv"
points_geojson_path = DATA_PATH / "concession.geojson"
GITHUB_GEOJSON_URL = "https://raw.githubusercontent.com/Moccamara/web_mapping/main/data/concession.geojson"

# Admin uploads CSV
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Import CSV Points")
    csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df_csv = pd.read_csv(csv_file)
        if {"LAT", "LON"}.issubset(df_csv.columns):
            df_csv = df_csv.dropna(subset=["LAT", "LON"])
            df_csv.to_csv(points_csv_path, index=False)  # save CSV in data folder

            # Convert automatically to GeoJSON in the same folder
            points_gdf = gpd.GeoDataFrame(
                df_csv,
                geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
                crs="EPSG:4326"
            )
            points_gdf.to_file(points_geojson_path, driver="GeoJSON")

# Load points for all users
if points_geojson_path.exists():
    points_gdf = gpd.read_file(points_geojson_path)
elif st.session_state.user_role != "Admin":
    # Fetch from GitHub if customer and local file missing
    try:
        points_gdf = gpd.read_file(GITHUB_GEOJSON_URL)
    except:
        points_gdf = None


# -----------------------------
# Load points for all users
# -----------------------------
points_gdf = None

# First try local GeoJSON
if points_geojson_path.exists():
    points_gdf = gpd.read_file(points_geojson_path)

# If local GeoJSON not found, try GitHub
else:
    try:
        r = requests.get(GITHUB_GEOJSON_URL)
        r.raise_for_status()
        temp_path = Path(tempfile.gettempdir()) / "concession.geojson"
        temp_path.write_bytes(r.content)
        points_gdf = gpd.read_file(temp_path)
        st.sidebar.info("🌐 Loaded points from GitHub.")
    except Exception as e:
        st.sidebar.warning(f"Could not load points from GitHub: {e}")

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=15)

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

# Add points if exists
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
                color=alt.Color("Variable:N", legend=alt.Legend(orient="right", title="Type")),
                tooltip=["idse_new", "Variable", "Population"]
            )
            .properties(height=130)
        )
        st.altair_chart(chart, use_container_width=True)

        st.subheader("👥 Sex (M / F)")
        if points_gdf is not None and {"Masculin", "Feminin"}.issubset(points_gdf.columns):
            pts = gpd.sjoin(points_gdf, gdf_idse, predicate="within")
            if not pts.empty:
                fig, ax = plt.subplots(figsize=(1, 1))
                ax.pie([pts["Masculin"].sum(), pts["Feminin"].sum()], labels=["M", "F"], autopct="%1.1f%%")
                st.pyplot(fig)

# =========================================================
# ADMIN EXPORT
# =========================================================
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 💾 Admin Export")
    export_btn = st.sidebar.button("Export Filtered Data to CSV")
    if export_btn:
        export_file = UPLOAD_DIR / f"export_{idse_selected}.csv"
        gdf_idse.to_csv(export_file, index=False)
        st.sidebar.success(f"Data exported as {export_file.name}")

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping** Developed with Streamlit, Folium & GeoPandas  
**CAMARA, PhD – Geomatics Engineering** © 2025
""")



