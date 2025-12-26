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
    st.session_state.csv_data = None  # Store uploaded CSV

# =========================================================
# LOGOUT
# =========================================================
def logout():
    st.session_state.auth_ok = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.csv_data = None
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
# LOAD GEOJSON
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
# SIDEBAR
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
idse_selected = st.sidebar.selectbox("Unit_Geo (SE)", idse_list)

gdf_idse = gdf if idse_selected == "No filter" else gdf[gdf["idse_new"] == idse_selected]

# =========================================================
# CSV UPLOAD (Admin only)
# =========================================================
if st.session_state.user_role == "Admin":
    st.sidebar.markdown("### 📥 Upload CSV")
    csv_file = st.sidebar.file_uploader("CSV (LAT, LON, Masculin, Feminin)", type="csv")

    if csv_file:
        df = pd.read_csv(csv_file).dropna(subset=["LAT", "LON"])
        points_gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["LON"], df["LAT"]),
            crs="EPSG:4326"
        )
        st.session_state.csv_data = points_gdf
else:
    points_gdf = None

# =========================================================
# MAP
# =========================================================
minx, miny, maxx, maxy = gdf_idse.total_bounds
m = folium.Map(location=[(miny + maxy)/2, (minx + maxx)/2], zoom_start=18)

folium.GeoJson(
    gdf_idse,
    style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.15},
    tooltip=folium.GeoJsonTooltip(fields=["idse_new", "pop_se", "pop_se_ct"])
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

with col_stats:
    # ---------------- BAR CHART ----------------
    if idse_selected != "No filter":
        df_bar = gdf_idse[["idse_new", "pop_se", "pop_se_ct"]].melt(
            id_vars="idse_new",
            var_name="Type",
            value_name="Population"
        )
        df_bar["Type"] = df_bar["Type"].replace({
            "pop_se": "Pop SE",
            "pop_se_ct": "Pop Actu"
        })
        st.altair_chart(
            alt.Chart(df_bar)
            .mark_bar()
            .encode(
                x="Type:N",
                y="Population:Q",
                color="Type:N"
            )
            .properties(height=150),
            use_container_width=True
        )

    # ---------------- PIE CHART ----------------
    st.subheader("Sex (M / F)")

    if st.session_state.user_role == "Admin":
        points_gdf = st.session_state.csv_data
        if points_gdf is None:
            st.warning("Upload CSV file.")
        else:
            points_gdf = points_gdf.to_crs(gdf_idse.crs)
            inside = gpd.sjoin(points_gdf, gdf_idse, predicate="within")

            if inside.empty:
                st.warning("No points inside SE.")
            else:
                inside["Masculin"] = pd.to_numeric(inside["Masculin"], errors="coerce").fillna(0)
                inside["Feminin"] = pd.to_numeric(inside["Feminin"], errors="coerce").fillna(0)

                m_total = int(inside["Masculin"].sum())
                f_total = int(inside["Feminin"].sum())

                if m_total + f_total > 0:
                    fig, ax = plt.subplots(figsize=(3, 3))
                    ax.pie([m_total, f_total], labels=["M", "F"], autopct="%1.1f%%", startangle=90)
                    ax.axis("equal")
                    st.pyplot(fig)

                    st.markdown(f"""
                    - 👨 **M**: {m_total}  
                    - 👩 **F**: {f_total}  
                    - 👥 **Total**: {m_total + f_total}
                    """)

    else:
        # ---------------- Aggregated stats for Customers ----------------
        st.info("Aggregated SE stats (from GeoJSON)")

        # Use pop_se / pop_se_ct as aggregated male/female for simplicity
        # Adjust if your data has separate M/F counts
        m_total = int(gdf_idse["pop_se"].sum())
        f_total = int(gdf_idse["pop_se_ct"].sum())

        if m_total + f_total > 0:
            fig, ax = plt.subplots(figsize=(3, 3))
            ax.pie([m_total, f_total], labels=["M", "F"], autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
            st.pyplot(fig)

            st.markdown(f"""
            - 👨 **M**: {m_total}  
            - 👩 **F**: {f_total}  
            - 👥 **Total**: {m_total + f_total}
            """)

# =========================================================
# FOOTER
# =========================================================
st.markdown("""
---
**Geospatial Enterprise Web Mapping**  
**Mahamadou CAMARA, PhD – Geomatics Engineering** © 2025
""")
