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
SE_URL = "https://raw.githubusercontent.com/Moccamara/web_mapping/main/data/SE.geojson"

try:
    gdf = gpd.read_file(SE_URL).to_crs(epsg=4326)
except Exception as e:
    st.error("Unable to load SE.geojson from GitHub")
    st.exception(e)
    st.stop()

# Normalize column names
gdf.columns = gdf.columns.str.lower().str.strip()

# Rename fields safely
gdf = gdf.rename(columns={
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
})

# Geometry validation
gdf = gdf[gdf.is_valid & ~gdf.is_empty]

# Ensure population fields exist
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
# CSV UPLOAD (POINTS) - Admin only
# =========================================================
points_gdf = None
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Import CSV Points")
    csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df_csv = pd.read_csv(csv_file)
        if {"LAT", "LON"}.issubset(df_csv.columns):
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
                                # "fontweight": "normal"
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
**CAMARA, PhD – Geomatics Engineering** © 2025
""")












