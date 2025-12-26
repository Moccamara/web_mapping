import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl, Draw
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
# LOGOUT
# =========================================================
def logout():
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.rerun()

# =========================================================
# LOGIN
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
# LOAD SE GEOJSON
# =========================================================
SE_URL = "https://raw.githubusercontent.com/Moccamara/web_mapping/master/data/SE.geojson"

@st.cache_data(show_spinner=False)
def load_se_data(url):
    gdf = gpd.read_file(url)
    gdf = gdf.to_crs(epsg=4326)
    gdf.columns = gdf.columns.str.lower().str.strip()

    gdf = gdf.rename(columns={
        "lregion": "region",
        "lcercle": "cercle",
        "lcommune": "commune"
    })

    for col in ["region", "cercle", "commune", "idse_new"]:
        if col not in gdf.columns:
            gdf[col] = ""

    for col in ["pop_se", "pop_se_ct"]:
        if col not in gdf.columns:
            gdf[col] = 0

    return gdf[gdf.is_valid & ~gdf.is_empty]

gdf = load_se_data(SE_URL)

# =========================================================
# SIDEBAR USER INFO
# =========================================================
with st.sidebar:
    st.markdown(f"**User:** {st.session_state.username} ({st.session_state.user_role})")
    if st.button("Logout"):
        logout()

# =========================================================
# FILTERS
# =========================================================
region = st.sidebar.selectbox("Region", sorted(gdf["region"].dropna().unique()))
gdf = gdf[gdf["region"] == region]

cercle = st.sidebar.selectbox("Cercle", sorted(gdf["cercle"].dropna().unique()))
gdf = gdf[gdf["cercle"] == cercle]

commune = st.sidebar.selectbox("Commune", sorted(gdf["commune"].dropna().unique()))
gdf = gdf[gdf["commune"] == commune]

idse_list = ["No filter"] + sorted(gdf["idse_new"].dropna().unique())
idse_selected = st.sidebar.selectbox("Unit_Geo", idse_list)

gdf_idse = gdf if idse_selected == "No filter" else gdf[gdf["idse_new"] == idse_selected]

# =========================================================
# CSV UPLOAD (ADMIN ONLY – INDEPENDENT FILE)
# =========================================================
points_gdf = None
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Upload CSV")
    csv_file = st.sidebar.file_uploader(
        "CSV (LAT, LON, Masculin, Feminin)", type="csv"
    )

    if csv_file:
        df = pd.read_csv(csv_file).dropna(subset=["LAT", "LON"])
        points_gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["LON"], df["LAT"]),
            crs="EPSG:4326"
        )

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
m = folium.Map(
    location=[(miny + maxy) / 2, (minx + maxx) / 2],
    zoom_start=18
)

folium.GeoJson(
    gdf_idse,
    style_function=lambda x: {
        "color": "blue",
        "weight": 2,
        "fillOpacity": 0.15
    },
    tooltip=folium.GeoJsonTooltip(
        fields=["idse_new", "pop_se", "pop_se_ct"]
    )
).add_to(m)

if points_gdf is not None:
    for _, r in points_gdf.iterrows():
        folium.CircleMarker(
            location=[r.geometry.y, r.geometry.x],
            radius=3,
            color="red",
            fill=True
        ).add_to(m)

MeasureControl().add_to(m)
Draw(export=True).add_to(m)

# =========================================================
# LAYOUT
# =========================================================
col_map, col_stats = st.columns((3, 1))

with col_map:
    st_folium(m, height=500, use_container_width=True)

# =========================================================
# STATS FUNCTIONS
# =========================================================
def compute_population_stats(gdf_idse, points_gdf, role):
    """
    Admin  → observed CSV points (independent file)
    Client → aggregated SE population
    """

    # ---------------- ADMIN ----------------
    if role == "Admin" and points_gdf is not None:
        inside = gpd.sjoin(
            points_gdf.to_crs(gdf_idse.crs),
            gdf_idse,
            predicate="intersects"
        )

        if not inside.empty and {"Masculin", "Feminin"}.issubset(inside.columns):
            m = pd.to_numeric(inside["Masculin"], errors="coerce").fillna(0).sum()
            f = pd.to_numeric(inside["Feminin"], errors="coerce").fillna(0).sum()
            return int(m), int(f), int(m + f), "Observed (CSV points)"

    # ---------------- CUSTOMER ----------------
    total = int(gdf_idse["pop_se"].sum())
    m = int(total * 0.5)
    f = total - m

    return m, f, total, "Estimated (SE population)"

# =========================================================
# STATS PANEL
# =========================================================
with col_stats:

    # -------- BAR CHART (SE) --------
    if idse_selected != "No filter":
        df_long = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].melt(
            id_vars="idse_new",
            var_name="Type",
            value_name="Population"
        )
        df_long["Type"] = df_long["Type"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })

        st.altair_chart(
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x="Type:N",
                y="Population:Q",
                color="Type:N"
            )
            .properties(height=150),
            use_container_width=True
        )

    # -------- PIE CHART --------
    st.subheader("Population by Sex")

    m, f, total, source = compute_population_stats(
        gdf_idse,
        points_gdf,
        st.session_state.user_role
    )

    if total == 0:
        st.warning("No population data available.")
    else:
        fig, ax = plt.subplots(figsize=(3, 3))
        ax.pie(
            [m, f],
            labels=["M", "F"],
            autopct="%1.1f%%",
            startangle=90
        )
        ax.axis("equal")
        st.pyplot(fig)

        st.caption(f"Source: {source}")

        st.markdown(f"""
        - 👨 **M**: {m}  
        - 👩 **F**: {f}  
        - 👥 **Total**: {total}
        """)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping**  
**Mahamadou CAMARA, PhD – Geomatics Engineering** © 2025
""")


# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping**  
**Mahamadou CAMARA, PhD – Geomatics Engineering** © 2025
""")

