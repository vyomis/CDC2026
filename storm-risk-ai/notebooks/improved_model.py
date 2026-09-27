import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = SCRIPT_DIR.parent / "data" / "processed"

MASTER_PATH = PROCESSED_DIR / "storms_master_2000_2025.csv"
CENSUS_PATH = PROCESSED_DIR / "nc_county_census.csv"

if not MASTER_PATH.exists():
    raise FileNotFoundError(
        f"Could not find master dataset at: {MASTER_PATH.resolve()}"
    )

if not CENSUS_PATH.exists():
    raise FileNotFoundError(
        f"Could not find Census dataset at: {CENSUS_PATH.resolve()}\n"
        "Expected columns: CZ_NAME, poverty_rate, median_income, "
        "mobile_home_rate, no_vehicle_rate"
    )

# ---------------------------------------------------------
# LOAD + FILTER NOAA DATA
# ---------------------------------------------------------

print("--- Loading Master Dataset ---")
master = pd.read_csv(MASTER_PATH, low_memory=False)

TARGET_EVENTS = [
    "Tornado",
    "Flash Flood",
    "Flood",
    "Thunderstorm Wind",
    "Hail",
]

nc = master[
    (master["STATE"] == "NORTH CAROLINA")
    & (master["EVENT_TYPE"].isin(TARGET_EVENTS))
].copy()

print(f"Filtered NC dataset shape: {nc.shape}")

# ---------------------------------------------------------
# CLEAN PROPERTY DAMAGE
# ---------------------------------------------------------

def convert_damage(value):
    if pd.isna(value):
        return 0.0

    val = str(value).strip().upper()

    if val in ["", "0", "NONE", "NAN"]:
        return 0.0

    multiplier = 1

    if val.endswith("K"):
        multiplier = 1_000
        val = val[:-1]
    elif val.endswith("M"):
        multiplier = 1_000_000
        val = val[:-1]
    elif val.endswith("B"):
        multiplier = 1_000_000_000
        val = val[:-1]

    try:
        return float(val) * multiplier
    except ValueError:
        return 0.0


nc["PROPERTY_DAMAGE_NUM"] = nc["DAMAGE_PROPERTY"].apply(convert_damage)

# High-impact storm = at least $100,000 in property damage
DAMAGE_THRESHOLD = 100_000
nc["HIGH_IMPACT"] = (
    nc["PROPERTY_DAMAGE_NUM"] >= DAMAGE_THRESHOLD
).astype(int)

# ---------------------------------------------------------
# CLEAN DATE / LOCATION FIELDS
# ---------------------------------------------------------

nc["BEGIN_DATE_TIME"] = pd.to_datetime(
    nc["BEGIN_DATE_TIME"],
    errors="coerce"
)

nc["YEAR"] = nc["BEGIN_DATE_TIME"].dt.year
nc["MONTH"] = nc["BEGIN_DATE_TIME"].dt.month

nc = nc.dropna(subset=["YEAR", "CZ_NAME"]).copy()

nc["YEAR"] = nc["YEAR"].astype(int)
nc["CZ_NAME"] = (
    nc["CZ_NAME"]
    .astype(str)
    .str.upper()
    .str.strip()
)

nc["MAGNITUDE"] = pd.to_numeric(
    nc["MAGNITUDE"],
    errors="coerce"
).fillna(0)

# Save cleaned event-level file
nc.to_csv(
    PROCESSED_DIR / "nc_storms_clean.csv",
    index=False
)

# ---------------------------------------------------------
# LOAD REAL CENSUS / ACS COUNTY FEATURES
# ---------------------------------------------------------

print("\n--- Loading County Vulnerability Features ---")

census_df = pd.read_csv(CENSUS_PATH)

census_df["CZ_NAME"] = (
    census_df["CZ_NAME"]
    .astype(str)
    .str.upper()
    .str.strip()
)

required_census_cols = [
    "CZ_NAME",
    "poverty_rate",
]

missing = [
    col for col in required_census_cols
    if col not in census_df.columns
]

if missing:
    raise ValueError(
        f"Missing required Census columns: {missing}"
    )

# ---------------------------------------------------------
# CONVERT STORM EVENTS -> COUNTY-YEAR DATASET
# ---------------------------------------------------------

print("\n--- Building County-Year Dataset ---")

county_year = (
    nc.groupby(["CZ_NAME", "YEAR"])
    .agg(
        events_this_year=("EVENT_ID", "count"),
        high_impacts_this_year=("HIGH_IMPACT", "sum"),
        avg_damage_this_year=("PROPERTY_DAMAGE_NUM", "mean"),
        max_damage_this_year=("PROPERTY_DAMAGE_NUM", "max"),
        avg_magnitude=("MAGNITUDE", "mean"),
    )
    .reset_index()
)

# Create rows even for county-years with zero target storms
all_counties = sorted(nc["CZ_NAME"].dropna().unique())
all_years = np.arange(
    int(nc["YEAR"].min()),
    int(nc["YEAR"].max()) + 1
)

grid = pd.MultiIndex.from_product(
    [all_counties, all_years],
    names=["CZ_NAME", "YEAR"]
).to_frame(index=False)

county_year = grid.merge(
    county_year,
    on=["CZ_NAME", "YEAR"],
    how="left"
)

storm_cols = [
    "events_this_year",
    "high_impacts_this_year",
    "avg_damage_this_year",
    "max_damage_this_year",
    "avg_magnitude",
]

county_year[storm_cols] = (
    county_year[storm_cols]
    .fillna(0)
)

# Add county vulnerability features
county_year = county_year.merge(
    census_df[required_census_cols],
    on="CZ_NAME",
    how="left"
)

# ---------------------------------------------------------
# HISTORICAL 5-YEAR FEATURES
# ---------------------------------------------------------

print("\n--- Creating 5-Year Historical Features ---")

county_year = county_year.sort_values(
    ["CZ_NAME", "YEAR"]
).reset_index(drop=True)

county_year["storms_past_5yr"] = (
    county_year
    .groupby("CZ_NAME")["events_this_year"]
    .transform(
        lambda x: x.shift(1)
        .rolling(5, min_periods=1)
        .sum()
    )
)

county_year["high_impacts_past_5yr"] = (
    county_year
    .groupby("CZ_NAME")["high_impacts_this_year"]
    .transform(
        lambda x: x.shift(1)
        .rolling(5, min_periods=1)
        .sum()
    )
)

county_year["avg_damage_past_5yr"] = (
    county_year
    .groupby("CZ_NAME")["avg_damage_this_year"]
    .transform(
        lambda x: x.shift(1)
        .rolling(5, min_periods=1)
        .mean()
    )
)

county_year[
    [
        "storms_past_5yr",
        "high_impacts_past_5yr",
        "avg_damage_past_5yr",
    ]
] = county_year[
    [
        "storms_past_5yr",
        "high_impacts_past_5yr",
        "avg_damage_past_5yr",
    ]
].fillna(0)

# ---------------------------------------------------------
# FUTURE TARGET
# ---------------------------------------------------------

# Target:
# 1 if the county has at least one >= $100k storm NEXT year
next_year_high_impacts = (
    county_year
    .groupby("CZ_NAME")["high_impacts_this_year"]
    .shift(-1)
)

# IMPORTANT:
# The final year has no observed "next year", so its target is unknown.
county_year["HIGH_IMPACT_NEXT_YEAR"] = (
    next_year_high_impacts.gt(0)
    .astype("Int64")
)

county_year.loc[
    next_year_high_impacts.isna(),
    "HIGH_IMPACT_NEXT_YEAR"
] = pd.NA

county_year.to_csv(
    PROCESSED_DIR / "nc_county_year_dataset.csv",
    index=False
)

# ---------------------------------------------------------
# FUTURE MODEL FEATURES
# ---------------------------------------------------------

future_features = [
    "poverty_rate",
    "storms_past_5yr",
    "high_impacts_past_5yr",
    "avg_damage_past_5yr",
]

model_df = county_year.dropna(
    subset=["HIGH_IMPACT_NEXT_YEAR"]
).copy()

X = model_df[future_features].fillna(0)
y = model_df["HIGH_IMPACT_NEXT_YEAR"].astype(int)

# ---------------------------------------------------------
# TIME-BASED TRAIN / VALIDATION / TEST SPLIT
# ---------------------------------------------------------

# Since the target is "next year", a 2024 row predicts 2025.
train_mask = model_df["YEAR"] <= 2020
val_mask = (
    (model_df["YEAR"] >= 2021)
    & (model_df["YEAR"] <= 2022)
)
test_mask = model_df["YEAR"] >= 2023

X_train = X.loc[train_mask]
y_train = y.loc[train_mask]

X_val = X.loc[val_mask]
y_val = y.loc[val_mask]

X_test = X.loc[test_mask]
y_test = y.loc[test_mask]

print("\nDataset Split Sizes:")
print(f"Train:      {len(X_train)}")
print(f"Validation: {len(X_val)}")
print(f"Test:       {len(X_test)}")

# ---------------------------------------------------------
# EVALUATION FUNCTION
# ---------------------------------------------------------

def evaluate(name, model, X_t, y_t):
    preds = model.predict(X_t)
    probs = model.predict_proba(X_t)[:, 1]

    print(f"\n================ {name} ================")
    print(f"Accuracy:  {accuracy_score(y_t, preds):.4f}")
    print(
        f"Precision: "
        f"{precision_score(y_t, preds, zero_division=0):.4f}"
    )
    print(
        f"Recall:    "
        f"{recall_score(y_t, preds, zero_division=0):.4f}"
    )
    print(
        f"F1 Score:  "
        f"{f1_score(y_t, preds, zero_division=0):.4f}"
    )

    if len(np.unique(y_t)) > 1:
        print(
            f"ROC-AUC:   "
            f"{roc_auc_score(y_t, probs):.4f}"
        )
    else:
        print("ROC-AUC:   unavailable (only one class in test set)")

    print("\nConfusion Matrix:")
    print(confusion_matrix(y_t, preds))


# ---------------------------------------------------------
# TRAIN MODELS
# ---------------------------------------------------------

rf = RandomForestClassifier(
    n_estimators=300,
    class_weight="balanced",
    random_state=42
)

rf.fit(X_train, y_train)
evaluate("Random Forest - Next Year", rf, X_test, y_test)

gb_model = GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.05,
    random_state=42
)

gb_model.fit(X_train, y_train)
evaluate("Gradient Boosting - Next Year", gb_model, X_test, y_test)

# ---------------------------------------------------------
# SHAP EXPLAINABILITY
# ---------------------------------------------------------

print("\n--- Generating SHAP Plot ---")

explainer = shap.TreeExplainer(gb_model)
shap_values = explainer(X_test)

plt.figure(figsize=(10, 6))
shap.summary_plot(
    shap_values,
    X_test,
    show=False
)

plt.tight_layout()

shap_out = PROCESSED_DIR / "shap_future_risk_summary.png"
plt.savefig(shap_out, dpi=150, bbox_inches="tight")
plt.close()

print(
    f"Saved SHAP summary plot to: "
    f"{shap_out.resolve()}"
)

# ---------------------------------------------------------
# CURRENT VULNERABILITY SCORE
# ---------------------------------------------------------

print("\n--- Calculating Current Vulnerability Scores ---")

latest_year = int(county_year["YEAR"].max())

latest_profiles = county_year[
    county_year["YEAR"] == latest_year
].copy()

vulnerability_cols = [
    "poverty_rate",
    "storms_past_5yr",
    "high_impacts_past_5yr",
    "avg_damage_past_5yr",
]

# Fill missing county values using medians
for col in vulnerability_cols:
    latest_profiles[col] = latest_profiles[col].fillna(
        county_year[col].median()
    )


# Normalize risk-increasing vulnerability factors
vuln_scaler = MinMaxScaler()

scaled_vulnerability = vuln_scaler.fit_transform(
    latest_profiles[vulnerability_cols]
)

scaled_vulnerability = pd.DataFrame(
    scaled_vulnerability,
    columns=vulnerability_cols,
    index=latest_profiles.index
)



# Equal-weight current vulnerability score
latest_profiles["vulnerability_score"] = (
    scaled_vulnerability.mean(axis=1) * 100
).round(1)

# ---------------------------------------------------------
# NEXT-YEAR PREDICTION FOR EACH COUNTY
# ---------------------------------------------------------

latest_X = (
    latest_profiles[future_features]
    .fillna(0)
)

latest_profiles["future_probability"] = (
    gb_model.predict_proba(latest_X)[:, 1]
)

latest_profiles["future_risk_score"] = (
    latest_profiles["future_probability"] * 100
).round(1)

# ---------------------------------------------------------
# FINAL COMBINED COUNTY RISK SCORE
# ---------------------------------------------------------

CURRENT_WEIGHT = 0.50
FUTURE_WEIGHT = 0.50

latest_profiles["overall_risk_score"] = (
    CURRENT_WEIGHT
    * latest_profiles["vulnerability_score"]
    +
    FUTURE_WEIGHT
    * latest_profiles["future_risk_score"]
).round(1)

latest_profiles["risk_level"] = pd.cut(
    latest_profiles["overall_risk_score"],
    bins=[-1, 39, 69, 100],
    labels=["Low", "Medium", "High"]
)

prediction_year = latest_year + 1

latest_profiles["prediction_year"] = prediction_year

final_county_risk = latest_profiles[
    [
        "CZ_NAME",
        "YEAR",
        "prediction_year",
        "vulnerability_score",
        "future_probability",
        "future_risk_score",
        "overall_risk_score",
        "risk_level",
        "storms_past_5yr",
        "high_impacts_past_5yr",
        "avg_damage_past_5yr",
        "poverty_rate",
    ]
].sort_values(
    "overall_risk_score",
    ascending=False
)

# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------

output_path = (
    PROCESSED_DIR
    / f"nc_county_risk_scores_{prediction_year}.csv"
)

final_county_risk.to_csv(
    output_path,
    index=False
)

print(
    f"\nSaved county risk scores to: "
    f"{output_path.resolve()}"
)

print(
    f"\n--- Top 10 NC County Risk Scores "
    f"for {prediction_year} ---"
)

print(
    final_county_risk[
        [
            "CZ_NAME",
            "vulnerability_score",
            "future_risk_score",
            "overall_risk_score",
            "risk_level",
        ]
    ].head(10).to_string(index=False)
)

print(
    "\nInterpretation:\n"
    "- vulnerability_score = current relative county vulnerability (0-100)\n"
    "- future_risk_score = model probability of >=1 high-impact storm next year (0-100)\n"
    "- overall_risk_score = 50% current vulnerability + 50% future risk\n"
    f"- high impact = at least ${DAMAGE_THRESHOLD:,.0f} in property damage"
)
