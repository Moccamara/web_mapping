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
st.set_page_config(layout="wide")
st.title("🌍 Geospatial Enterprise Solution")

# =========================================================
# 🔐 PASSWORD AUTHENTICATION
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

try:
    PASSWORD = st.secrets["auth"]["dashboard_password"]
except Exception:
    PASSWORD = "mocc2025"

if not st.session_state.auth_ok:
    with st.sidebar:
        st.header("🔐 Authentication")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if pwd == PASSWORD:
                st.session_state.auth_ok = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")
    st.stop()

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

rename_map = {
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
}
gdf = gdf.rename(columns=rename_map)
gdf = gdf[gdf.is_valid & ~gdf.is_empty]

for col in ["pop_se", "pop_se_ct"]:
    if col not in gdf.columns:
        gdf[col] = 0

# =========================================================
# SIDEBAR FILTERS
# =========================================================
with st.sidebar:
    st.image("logo/logo_wgv.png", width=200)
    st.markdown("### 🗂️ Attribute Query")

region = st.sidebar.selectbox("Region", sorted(gdf["region"].dropna().unique()))
gdf_r = gdf[gdf["region"] == region]

cercle = st.sidebar.selectbox("Cercle", sorted(gdf_r["cercle"].dropna().unique()))
gdf_c = gdf_r[gdf_r["cercle"] == cercle]

commune = st.sidebar.selectbox("Commune", sorted(gdf_c["commune"].dropna().unique()))
gdf_commune = gdf_c[gdf_c["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].dropna().unique())
idse_selected = st.sidebar.selectbox("IDSE_NEW", idse_list)

gdf_idse = gdf_commune.copy()
if idse_selected != "No filtre":
    gdf_idse = gdf_commune[gdf_commune["idse_new"] == idse_selected]

# =========================================================
# CSV UPLOAD (POINTS) ✅ FIXED
# =========================================================
st.sidebar.markdown("### 📥 Import CSV Points")
csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])

points_gdf = None
if csv_file:
    df_csv = pd.read_csv(csv_file)

    if {"LAT", "LON"}.issubset(df_csv.columns):
        # ✅ FIX: force numeric & drop NaNs
        df_csv["LAT"] = pd.to_numeric(df_csv["LAT"], errors="coerce")
        df_csv["LON"] = pd.to_numeric(df_csv["LON"], errors="coerce")
        df_csv = df_csv.dropna(subset=["LAT", "LON"])

        points_gdf = gpd.GeoDataFrame(
            df_csv,
            geometry=gpd.points_from_xy(df_csv["LON"], df_csv["LAT"]),
            crs="EPSG:4326"
        )

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
    style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.1},
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
col_map, col_chart = st.columns([4, 1])

with col_map:
    st_folium(m, height=400, width=650)

with col_chart:
    if idse_selected == "No filtre":
        st.info("Select an IDSE")
    else:
        df_long = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].melt(
            id_vars="idse_new",
            value_vars=["pop_se", "pop_se_ct"],
            var_name="Type",
            value_name="Population"
        )

        df_long["Type"] = df_long["Type"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })

        chart = alt.Chart(df_long).mark_bar().encode(
            x="idse_new:N",
            xOffset="Type:N",
            y="Population:Q",
            color=alt.Color("Type:N", legend=alt.Legend(orient="right")),
            tooltip=["Type", "Population"]
        ).properties(height=120)

        st.altair_chart(chart, use_container_width=True)

        st.subheader("Sex (M / F)")
        if points_gdf is not None and {"Masculin", "Feminin"}.issubset(points_gdf.columns):
            pts = gpd.sjoin(points_gdf, gdf_idse, predicate="within")
            if not pts.empty:
                m_val = int(pts["Masculin"].sum())
                f_val = int(pts["Feminin"].sum())

                fig, ax = plt.subplots(figsize=(3, 3))
                ax.pie([m_val, f_val], labels=["M", "F"], autopct="%1.1f%%")
                st.pyplot(fig)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
**Geospatial Enterprise Web Mapping** Developed with Streamlit, Folium & GeoPandas  
**CAMARA, PhD – Geomatics Engineering** © 2025
""")
