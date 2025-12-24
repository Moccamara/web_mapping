import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
from pathlib import Path

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

gdf = gpd.read_file(geo_file)
gdf.columns = gdf.columns.str.lower().str.strip()

rename_map = {
    "lregion": "region",
    "lcercle": "cercle",
    "lcommune": "commune",
    "idse_new": "idse_new"
}
gdf = gdf.rename(columns=rename_map)

# Geometry cleaning
gdf = gdf.to_crs(epsg=4326)
gdf = gdf[gdf.is_valid & ~gdf.is_empty]

# Column safety
required_cols = ["region", "cercle", "commune", "idse_new"]
missing = [c for c in required_cols if c not in gdf.columns]
if missing:
    st.error(f"Missing columns: {missing}")
    st.stop()

# =========================================================
# SIDEBAR – FILTERS
# =========================================================
with st.sidebar:
    st.image("logo/logo_wgv.png", width=200)
    st.markdown("### 🗂️ Attribute Query")

regions = sorted(gdf["region"].dropna().unique())
region = st.sidebar.selectbox("Region", regions)
gdf_region = gdf[gdf["region"] == region]

cercles = sorted(gdf_region["cercle"].dropna().unique())
cercle = st.sidebar.selectbox("Cercle", cercles)
gdf_cercle = gdf_region[gdf_region["cercle"] == cercle]

communes = sorted(gdf_cercle["commune"].dropna().unique())
commune = st.sidebar.selectbox("Commune", communes)
gdf_commune = gdf_cercle[gdf_cercle["commune"] == commune]

idse_list = ["No filtre"] + sorted(gdf_commune["idse_new"].dropna().unique())
idse_selected = st.sidebar.selectbox("IDSE_NEW (optional)", idse_list)

gdf_idse = gdf_commune.copy()
if idse_selected != "No filtre":
    gdf_idse = gdf_commune[gdf_commune["idse_new"] == idse_selected]

# =========================================================
# MAP CENTER & BOUNDS
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# =========================================================
# FOLIUM MAP
# =========================================================
m = folium.Map(location=[center_lat, center_lon], zoom_start=15)

folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    name="Satellite (Esri)",
    attr="Esri",
    overlay=False
).add_to(m)

# Auto zoom to selection
m.fit_bounds([[miny, minx], [maxy, maxx]])

# =========================================================
# IDSE POLYGON LAYER
# =========================================================
folium.GeoJson(
    gdf_idse,
    name="IDSE Polygons",
    style_function=lambda x: {
        "color": "blue",
        "weight": 2,
        "fillOpacity": 0.1
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new", "commune", "cercle", "region"],
        aliases=["IDSE", "Commune", "Cercle", "Region"],
        sticky=True
    )
).add_to(m)

# =========================================================
# TOOLS
# =========================================================
MeasureControl(
    position="topright",
    primary_length_unit="meters",
    primary_area_unit="sqmeters"
).add_to(m)

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

folium.LayerControl(collapsed=True).add_to(m)

# =========================================================
# LEGEND (COLLAPSIBLE)
# =========================================================
legend_html = """
<div style="position: fixed; bottom: 40px; left: 40px; z-index:9999;">
<details>
<summary style="background:white;padding:6px;border:2px solid grey;cursor:pointer;">
Legend
</summary>
<div style="background:white;padding:10px;border:2px solid grey;width:200px;">
<span style="color:blue;">■</span> IDSE Boundary<br>
</div>
</details>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# =========================================================
# DISPLAY MAP
# =========================================================
st.subheader(
    f"🗺️ Commune: {commune}"
    if idse_selected == "No filtre"
    else f"🗺️ IDSE: {idse_selected}"
)

st_folium(m, height=380, width=650)


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
**Project:** Geospatial Enterprise Web Mapping Developed with Streamlit, Folium & GeoPandas  
**CAMARA, PhD – Geomatics Engineering** © 2025
""")

