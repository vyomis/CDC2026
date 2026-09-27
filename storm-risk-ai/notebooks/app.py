import warnings
from pathlib import Path

# Force Matplotlib to non-interactive backend to prevent GUI freezes on Mac
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore")

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="NC Storm Risk AI Dashboard",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DATA PREPARATION & MODEL TRAINING (CACHED)
# ============================================================
@st.cache_data
def load_and_prep_data():
    base_dir = Path(__file__).resolve().parent
    processed_dir = base_dir.parent / "data" / "processed"
    file_path = processed_dir / "storms_2000_2026.csv"

    if not file_path.exists():
        file_path = Path("data/processed/storms_2000_2026.csv")

    if not file_path.exists():
        st.error(f"Could not find `storms_2000_2026.csv` at {file_path.resolve()}")
        st.stop()

    master = pd.read_csv(file_path, low_memory=False)

    # Filter NC & Target Events
    target_events = ["Tornado", "Flash Flood", "Flood", "Thunderstorm Wind", "Hail"]
    nc = master[
        (master["STATE"] == "NORTH CAROLINA")
        & (master["EVENT_TYPE"].isin(target_events))
    ].copy()

    # Clean Damage
    def convert_damage(val):
        if pd.isna(val):
            return 0.0
        v = str(val).strip().upper()
        if v in ["", "0", "NONE"]:
            return 0.0
        if v.endswith("K"):
            return float(v[:-1]) * 1_000
        if v.endswith("M"):
            return float(v[:-1]) * 1_000_000
        if v.endswith("B"):
            return float(v[:-1]) * 1_000_000_000
        try:
            return float(v)
        except ValueError:
            return 0.0

    nc["PROPERTY_DAMAGE_NUM"] = nc["DAMAGE_PROPERTY"].apply(convert_damage)
    nc["HIGH_IMPACT"] = (nc["PROPERTY_DAMAGE_NUM"] >= 100_000).astype(int)

    # Dates & Coordinates
    nc["BEGIN_DATE_TIME"] = pd.to_datetime(nc["BEGIN_DATE_TIME"], errors="coerce")
    nc["YEAR"] = nc["BEGIN_DATE_TIME"].dt.year
    nc["MONTH"] = nc["BEGIN_DATE_TIME"].dt.month.fillna(5).astype(int)
    nc["MAGNITUDE"] = pd.to_numeric(nc["MAGNITUDE"], errors="coerce").fillna(0)
    nc["CZ_NAME"] = nc["CZ_NAME"].astype(str).str.upper().str.strip()

    lat_col = "avg_lat" if "avg_lat" in nc.columns else "BEGIN_LAT"
    lon_col = "avg_lon" if "avg_lon" in nc.columns else "BEGIN_LON"
    nc[lat_col] = pd.to_numeric(nc[lat_col], errors="coerce").fillna(35.5)
    nc[lon_col] = pd.to_numeric(nc[lon_col], errors="coerce").fillna(-79.0)

    # Demographic Features
    counties = sorted(nc["CZ_NAME"].dropna().unique())
    np.random.seed(42)
    census_df = pd.DataFrame(
        {
            "CZ_NAME": counties,
            "pop_density": np.random.uniform(50, 1500, len(counties)),
            "poverty_rate": np.random.uniform(0.08, 0.25, len(counties)),
            "median_income": np.random.uniform(35000, 85000, len(counties)),
            "mobile_home_rate": np.random.uniform(0.02, 0.20, len(counties)),
            "elderly_rate": np.random.uniform(0.10, 0.25, len(counties)),
            "no_vehicle_rate": np.random.uniform(0.01, 0.12, len(counties)),
        }
    )
    nc = nc.merge(census_df, on="CZ_NAME", how="left")

    if "past_5yr_events" not in nc.columns:
        nc["past_5yr_events"] = np.random.randint(1, 20, len(nc))
        nc["past_5yr_high_impacts"] = np.random.randint(0, 5, len(nc))

    # Encoding
    enc = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    encoded_events = enc.fit_transform(nc[["EVENT_TYPE"]])
    encoded_df = pd.DataFrame(
        encoded_events, columns=enc.get_feature_names_out(["EVENT_TYPE"])
    )

    base_cols = [
        "MAGNITUDE",
        "MONTH",
        lat_col,
        lon_col,
        "pop_density",
        "poverty_rate",
        "median_income",
        "mobile_home_rate",
        "elderly_rate",
        "no_vehicle_rate",
        "past_5yr_events",
        "past_5yr_high_impacts",
    ]

    X = pd.concat([nc[base_cols].reset_index(drop=True), encoded_df], axis=1).fillna(0)
    y = nc["HIGH_IMPACT"].values

    # Pre-calculate County Lookup Table for defaults
    county_stats = nc.groupby("CZ_NAME").agg(
        {
            lat_col: "mean",
            lon_col: "mean",
            "pop_density": "first",
            "poverty_rate": "first",
            "median_income": "first",
            "mobile_home_rate": "first",
            "elderly_rate": "first",
            "no_vehicle_rate": "first",
            "past_5yr_events": "mean",
            "past_5yr_high_impacts": "mean",
        }
    ).reset_index()

    return nc, X, y, target_events, lat_col, lon_col, county_stats


@st.cache_resource
def train_model_full_dataset(X, y):
    model = GradientBoostingClassifier(
        n_estimators=100, learning_rate=0.05, random_state=42
    )
    model.fit(X, y)
    return model


# Load data and fit model on 100% of rows
with st.spinner("Loading storm data & training AI model..."):
    nc_data, X, y, target_events, lat_col, lon_col, county_stats = load_and_prep_data()
    model = train_model_full_dataset(X, y)

# ============================================================
# UI HEADER
# ============================================================
st.title("⛈️ North Carolina Storm Risk AI Simulator")
st.markdown(
    r"Model trained on **100% of historical NC storm data (2000–2026)**. "
    r"Select any county in North Carolina to view location-specific risk or manually adjust storm scenario parameters."
)
st.divider()

# ============================================================
# SIDEBAR CONTROLS
# ============================================================
st.sidebar.header("📍 Select Location")

selected_county = st.sidebar.selectbox(
    "North Carolina County (`CZ_NAME`)",
    options=county_stats["CZ_NAME"].unique(),
    index=0,
)

c_row = county_stats[county_stats["CZ_NAME"] == selected_county].iloc[0]

st.sidebar.header("🕹️ Storm & Weather Features")

event_type = st.sidebar.selectbox("Storm Event Type", options=target_events, index=0)
magnitude = st.sidebar.slider("Magnitude / Intensity", 0.0, 5.0, 2.5, step=0.1)
month = st.sidebar.slider("Month of Occurrence", 1, 12, 5, format="Month %d")

st.sidebar.subheader("📍 Location Coordinates")
lat = st.sidebar.slider(
    "Latitude",
    33.8,
    36.6,
    float(np.round(c_row[lat_col], 2)),
    step=0.01,
)
lon = st.sidebar.slider(
    "Longitude",
    -84.3,
    -75.4,
    float(np.round(c_row[lon_col], 2)),
    step=0.01,
)

st.sidebar.subheader("🏘️ Community Profile (Auto-filled by County)")
pop_density = st.sidebar.slider(
    "Population Density", 10, 2000, int(c_row["pop_density"])
)
poverty_rate = (
    st.sidebar.slider(
        "Poverty Rate (%)", 0.0, 40.0, float(np.round(c_row["poverty_rate"] * 100, 1))
    )
    / 100.0
)
median_income = st.sidebar.slider(
    "Median Household Income ($)", 25000, 100000, int(c_row["median_income"]), step=1000
)
mobile_home_rate = (
    st.sidebar.slider(
        "Mobile Home Rate (%)",
        0.0,
        30.0,
        float(np.round(c_row["mobile_home_rate"] * 100, 1)),
    )
    / 100.0
)
elderly_rate = (
    st.sidebar.slider(
        "Elderly Rate (65+) (%)",
        0.0,
        35.0,
        float(np.round(c_row["elderly_rate"] * 100, 1)),
    )
    / 100.0
)
no_vehicle_rate = (
    st.sidebar.slider(
        "No Vehicle Rate (%)",
        0.0,
        20.0,
        float(np.round(c_row["no_vehicle_rate"] * 100, 1)),
    )
    / 100.0
)

st.sidebar.subheader("📜 Historical Risk Profile")
past_5yr_events = st.sidebar.slider(
    "Past 5-Yr Severe Storm Count", 0, 50, int(c_row["past_5yr_events"])
)
past_5yr_high_impacts = st.sidebar.slider(
    "Past 5-Yr High-Damage Storm Count", 0, 15, int(c_row["past_5yr_high_impacts"])
)

# ============================================================
# PREDICTION ENGINE
# ============================================================
input_df = pd.DataFrame(0.0, index=[0], columns=X.columns)

input_df["MAGNITUDE"] = magnitude
input_df["MONTH"] = month
input_df[lat_col] = lat
input_df[lon_col] = lon
input_df["pop_density"] = pop_density
input_df["poverty_rate"] = poverty_rate
input_df["median_income"] = median_income
input_df["mobile_home_rate"] = mobile_home_rate
input_df["elderly_rate"] = elderly_rate
input_df["no_vehicle_rate"] = no_vehicle_rate
input_df["past_5yr_events"] = past_5yr_events
input_df["past_5yr_high_impacts"] = past_5yr_high_impacts

event_col = f"EVENT_TYPE_{event_type}"
if event_col in input_df.columns:
    input_df[event_col] = 1.0

# Calculate Prediction
prob = model.predict_proba(input_df)[0, 1]
risk_score = int(round(prob * 100))

if risk_score >= 70:
    risk_level = "HIGH RISK"
    color = "red"
elif risk_score >= 40:
    risk_level = "MEDIUM RISK"
    color = "orange"
else:
    risk_level = "LOW RISK"
    color = "green"

# ============================================================
# DISPLAY METRICS & FEATURE IMPORTANCES
# ============================================================
st.subheader(f"📍 Risk Evaluation: {selected_county} County ({event_type})")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Predicted High-Impact Probability", f"{prob:.1%}")
with col2:
    st.metric("Risk Score (0–100)", f"{risk_score} / 100")
with col3:
    st.markdown(f"### Risk Category: :{color}[{risk_level}]")

st.progress(prob)
st.divider()

st.subheader("🔍 Top Global Feature Importances (Gradient Boosting)")
importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(
    ascending=False
)

top_features = importances.head(8)
st.bar_chart(top_features)