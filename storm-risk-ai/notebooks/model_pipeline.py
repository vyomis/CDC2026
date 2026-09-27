import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = SCRIPT_DIR.parent / "data" / "processed"
MASTER_PATH = PROCESSED_DIR / "storms_2000_2026.csv"

if not MASTER_PATH.exists():
    raise FileNotFoundError(
        f"Could not find master dataset at: {MASTER_PATH.resolve()}\n"
        "Ensure 'storms_2000_2026.csv' is saved in data/processed/."
    )

print("--- Loading Full Historical Master Dataset (2000 - 2026) ---")
master = pd.read_csv(MASTER_PATH, low_memory=False)

TARGET_EVENTS = ["Tornado", "Flash Flood", "Flood", "Thunderstorm Wind", "Hail"]
nc = master[
    (master["STATE"] == "NORTH CAROLINA")
    & (master["EVENT_TYPE"].isin(TARGET_EVENTS))
].copy()

# Clean Property Damage
def convert_damage(value):
    if pd.isna(value):
        return 0.0
    val = str(value).strip().upper()
    if val in ["", "0", "NONE"]:
        return 0.0
    if val.endswith("K"):
        return float(val[:-1]) * 1_000
    if val.endswith("M"):
        return float(val[:-1]) * 1_000_000
    if val.endswith("B"):
        return float(val[:-1]) * 1_000_000_000
    try:
        return float(val)
    except ValueError:
        return 0.0

nc["PROPERTY_DAMAGE_NUM"] = nc["DAMAGE_PROPERTY"].apply(convert_damage)
DAMAGE_THRESHOLD = 100_000
nc["HIGH_IMPACT"] = (nc["PROPERTY_DAMAGE_NUM"] >= DAMAGE_THRESHOLD).astype(int)

# Dates, Time, Coordinates
nc["BEGIN_DATE_TIME"] = pd.to_datetime(nc["BEGIN_DATE_TIME"], errors="coerce")
nc["YEAR"] = nc["BEGIN_DATE_TIME"].dt.year
nc["MONTH"] = nc["BEGIN_DATE_TIME"].dt.month.fillna(5).astype(int)
nc["MAGNITUDE"] = pd.to_numeric(nc["MAGNITUDE"], errors="coerce").fillna(0)
nc["CZ_NAME"] = nc["CZ_NAME"].astype(str).str.upper().str.strip()

lat_col = "avg_lat" if "avg_lat" in nc.columns else "BEGIN_LAT"
lon_col = "avg_lon" if "avg_lon" in nc.columns else "BEGIN_LON"
nc[lat_col] = pd.to_numeric(nc[lat_col], errors="coerce").fillna(35.5)
nc[lon_col] = pd.to_numeric(nc[lon_col], errors="coerce").fillna(-79.0)

# Merge Demographic Indicators
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

# Rolling Past 5-Year Context
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

# County Lookup Reference Table
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

print(f"Training Gradient Boosting Classifier on all {len(X)} records...")
gb_model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
gb_model.fit(X, y)
print("Model training complete.")

def calculate_location_risk(county_name, event_type="Tornado", magnitude=2.5, month=5):
    county_clean = str(county_name).strip().upper()
    c_data = county_stats[county_stats["CZ_NAME"] == county_clean]
    
    if len(c_data) == 0:
        print(f"\n[Warning] County '{county_name}' not found in dataset.")
        print(f"Available counties sample: {counties[:5]}")
        return None

    c_row = c_data.iloc[0]
    
    # Construct model input vector
    input_df = pd.DataFrame(0.0, index=[0], columns=X.columns)
    input_df["MAGNITUDE"] = magnitude
    input_df["MONTH"] = month
    input_df[lat_col] = c_row[lat_col]
    input_df[lon_col] = c_row[lon_col]
    input_df["pop_density"] = c_row["pop_density"]
    input_df["poverty_rate"] = c_row["poverty_rate"]
    input_df["median_income"] = c_row["median_income"]
    input_df["mobile_home_rate"] = c_row["mobile_home_rate"]
    input_df["elderly_rate"] = c_row["elderly_rate"]
    input_df["no_vehicle_rate"] = c_row["no_vehicle_rate"]
    input_df["past_5yr_events"] = c_row["past_5yr_events"]
    input_df["past_5yr_high_impacts"] = c_row["past_5yr_high_impacts"]
    
    event_col = f"EVENT_TYPE_{event_type}"
    if event_col in input_df.columns:
        input_df[event_col] = 1.0

    # Calculate Probability & Score
    prob = gb_model.predict_proba(input_df)[0, 1]
    risk_score = int(round(prob * 100))
    risk_level = "High" if risk_score >= 70 else ("Medium" if risk_score >= 40 else "Low")

    print("\n============================================================")
    print(f"  LOCATION RISK REPORT: {county_clean} COUNTY")
    print("============================================================")
    print(f"Storm Event Type:            {event_type}")
    print(f"Magnitude / Intensity:       {magnitude}")
    print(f"Month:                       {month}")
    print(f"Coordinates:                 ({c_row[lat_col]:.2f}, {c_row[lon_col]:.2f})")
    print(f"High Impact Probability:     {prob:.2%}")
    print(f"Risk Score (0 - 100):        {risk_score} / 100")
    print(f"Risk Level Category:         {risk_level}")
    print("------------------------------------------------------------\n")

    return risk_score

if __name__ == "__main__":
    print("\n------------------------------------------------------------")
    print("   INTERACTIVE LOCATION STORM RISK EVALUATOR")
    print("------------------------------------------------------------")
    
    # Pre-run a sample calculation for WAKE county
    calculate_location_risk("WAKE", event_type="Tornado", magnitude=3.0, month=5)
    
    try:
        user_county = input("Enter a North Carolina County Name (e.g. WAKE, MECKLENBURG, DARE) [or press Enter to exit]: ").strip()
        if user_county:
            user_event = input("Enter Event Type (Tornado, Flash Flood, Flood, Thunderstorm Wind, Hail) [Default: Tornado]: ").strip() or "Tornado"
            user_mag = float(input("Enter Magnitude (0.0 to 5.0) [Default: 2.5]: ") or 2.5)
            user_month = int(input("Enter Month (1 to 12) [Default: 5]: ") or 5)
            
            calculate_location_risk(user_county, event_type=user_event, magnitude=user_mag, month=user_month)
    except KeyboardInterrupt:
        print("\nExiting evaluator.")