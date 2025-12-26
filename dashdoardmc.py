import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
from shapely.geometry import Point

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
    "customer": {"password": "cust2025", "role": "Customer"},
}

# =========================================================
# SESSION INIT
# =========================================================
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None

# =========================================================
# LOGOUT FUNCTION
# =========================================================
def logout():
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.rerun()

# =========================================================
# HOME / LOGIN
# =========================================================
if not st.session_state.auth_ok:
    st.sidebar.header("🔐 Login")
    username = st.sidebar.selectbox("User", list(USERS.keys()))
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if password == USERS[username]["password"]:
            st.session_state.auth_ok = True
            st.session_state.username = username
            st.session_state.user_role = USERS[username]["role"]
            st.rerun()
        else:
            st.sidebar.error("❌ Incorrect password")
    st.stop()

# =========================================================
# LOAD SE POLYGONS
# =========================================================
SE_URL = "https://raw.githubusercontent.com/Moccamara/web_mapping/master/data/SE.geojson"

@st.cache_data(show_spinner=False)
def load_se_data(url):
    gdf = gpd.read_file(url)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)
    gdf.columns = gdf.columns.str.lower().str.strip()
    gdf = gdf.rename(
        columns={"lregion": "region", "lcercle": "cercle", "lcommune": "commune"}
    )
    gdf = gdf[gdf.is_valid & ~gdf.is_empty]
    for col in ["region", "cercle", "commune", "idse_new"]:
        if col not in gdf.columns:
            gdf[col] = ""
    for col in ["pop_se", "pop_se_ct"]:
        if col not in gdf.columns:
            gdf[col] = 0
    return gdf

try:
    gdf = load_se_data(SE_URL)
except Exception:
    st.error("❌ Unable to load SE.geojson from GitHub")
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.image("logo/logo_wgv.png", width=200)
    st.markdown(f"**Logged in as:** {st.session_state.username} ({st.session_state.user_role})")
    if st.button("Logout"):
        logout()

# =========================================================
# FILTERS
# =========================================================
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

    # -----------------------------
# Upload CSV Points (LAT, LON, Masculin, Feminin)
# -----------------------------
if st.session_state.user_role == "Admin":
st.sidebar.markdown("### 📥 Upload CSV Points")
csv_file = st.sidebar.file_uploader(
    "Upload CSV",
    type=["csv"],
    key="csv_points_uploader"
)
points_gdf = None
if csv_file:
    try:
        df_csv = pd.read_csv(csv_file)
        lat_col = "LAT"
        lon_col = "LON"

        df_csv = df_csv.dropna(subset=[lat_col, lon_col])

        if not df_csv.empty:
            points_gdf = gpd.GeoDataFrame(
                df_csv,
                geometry=gpd.points_from_xy(df_csv[lon_col], df_csv[lat_col]),
                crs="EPSG:4326"
            )
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")

# Add CSV points to the map
if points_gdf is not None and not points_gdf.empty:
    for _, row in points_gdf.iterrows():
        if pd.notna(row.geometry.x) and pd.notna(row.geometry.y):
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=2,
                color="red",
                fill=True,
                fill_opacity=0.8
            ).add_to(m)

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
m = folium.Map(location=[(miny + maxy)/2, (minx + maxx)/2], zoom_start=18)
folium.TileLayer("OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    name="Satellite",
    attr="Esri",
).add_to(m)
m.fit_bounds([[miny, minx], [maxy, maxx]])
folium.GeoJson(
    gdf_idse,
    name="IDSE",
    style_function=lambda x: {"color":"blue","weight":2,"fillOpacity":0.15},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new","pop_se","pop_se_ct"]),
).add_to(m)

if filtered_points is not None:
    for _, r in filtered_points.iterrows():
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

 # ---------------------------
    # Bar Chart (GeoJSON)
    # ---------------------------
    if idse_selected == "No filter":
        st.info("Select SE.")
    else:
        st.subheader("📊")

        # Prepare data
        df_geo_stats = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].copy()
        df_geo_stats["idse_new"] = df_geo_stats["idse_new"].astype(str)

        # Melt to long format
        df_long = df_geo_stats.melt(
            id_vars="idse_new",
            value_vars=["pop_se", "pop_se_ct"],
            var_name="Variable",
            value_name="Population"
        )

        df_long["Variable"] = df_long["Variable"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })

        # Bar chart with legend visible
        chart = (
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x=alt.X(
                    "idse_new:N",
                    title=None,
                    axis=alt.Axis(
                        labelAngle=0,
                        labelFontSize=10,
                        ticks=False
                    )
                ),
                xOffset="Variable:N",      # Bars side-by-side
                y=alt.Y("Population:Q", title=None),
                color=alt.Color(
                    "Variable:N",
                    title="Type",            # Name of legend
                    legend=alt.Legend(
                        orient="right",
                        labelFontSize=10,
                        titleFontSize=10,
                        padding=0
                    )
                ),
                tooltip=["idse_new", "Variable", "Population"]
            )
            .properties(width=80, height=120)
        )

        st.altair_chart(chart, use_container_width=True)

        # ---------------------------
        # Pie Chart (CSV: Masculin / Feminin)
        # ---------------------------
        st.subheader("Sex(M.F)")

        if points_gdf is None:
            st.warning("Select CSV file.")
        else:
            try:
                points_inside = gpd.sjoin(
                    points_gdf,
                    gdf_idse[["idse_new", "geometry"]],
                    predicate="within",
                    how="inner"
                )

                if points_inside.empty:
                    st.warning("NO SE selected.")
                else:
                    if not all(col in points_inside.columns for col in ["Masculin", "Feminin"]):
                        st.error("Le CSV doit contenir les colonnes: Masculin, Feminin")
                    else:
                        total_masculin = int(points_inside["Masculin"].sum())
                        total_feminin = int(points_inside["Feminin"].sum())
                        total_population = total_masculin + total_feminin

                        labels = ["M", "F"]
                        values = [total_masculin, total_feminin]

                        fig, ax = plt.subplots(figsize=(3.5, 3.5))
                        wedges, texts, autotexts = ax.pie(
                            values,
                            labels=labels,
                            autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else "",
                            textprops={'color': 'white', 'fontsize': 14}
                        )
                        
                        st.pyplot(fig)

                        st.markdown(f"""
                       
                        - 👨 M: **{total_masculin}**
                        - 👩 F: **{total_feminin}**
                        - 👥 Pop: **{total_population}**
                        """)

            except Exception as e:
                st.error(f"Erreur lors du pie chart : {e}")


# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping** Developed with Streamlit, Folium & GeoPandas  
**Mahamadou CAMARA, PhD – Geomatics Engineering** © 2025
""")




