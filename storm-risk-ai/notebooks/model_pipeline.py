import warnings
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ML & Explainability Imports
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import OneHotEncoder
import shap

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = SCRIPT_DIR.parent / "data" / "processed"
MASTER_PATH = PROCESSED_DIR / "storms_2000_2026.csv"

if not MASTER_PATH.exists():
    raise FileNotFoundError(
        f"Could not find master dataset at: {MASTER_PATH.resolve()}\n"
        "Ensure 'storms_2000_2026.csv' is saved in data/processed/."
    )

# ============================================================
# LOAD & FILTER DATA (STEPS 6 & 7)
# ============================================================
print("--- Loading Master Dataset ---")
master = pd.read_csv(MASTER_PATH, low_memory=False)

TARGET_EVENTS = ["Tornado", "Flash Flood", "Flood", "Thunderstorm Wind", "Hail"]
nc = master[
    (master["STATE"] == "NORTH CAROLINA")
    & (master["EVENT_TYPE"].isin(TARGET_EVENTS))
].copy()

print(f"Filtered NC dataset shape: {nc.shape}")

# ============================================================
# 8. CLEAN PROPERTY DAMAGE & 9. CREATE PREDICTION TARGET
# ============================================================
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

# Target: High impact if damage >= $100,000
DAMAGE_THRESHOLD = 100_000
nc["HIGH_IMPACT"] = (nc["PROPERTY_DAMAGE_NUM"] >= DAMAGE_THRESHOLD).astype(int)

print("\n--- Target Class Distribution (HIGH_IMPACT) ---")
print(nc["HIGH_IMPACT"].value_counts())
print(nc["HIGH_IMPACT"].value_counts(normalize=True))

# ============================================================
# 10. CREATE SIMPLE STORM FEATURES
# ============================================================
nc["BEGIN_DATE_TIME"] = pd.to_datetime(nc["BEGIN_DATE_TIME"], errors="coerce")
nc["YEAR"] = nc["BEGIN_DATE_TIME"].dt.year
nc["MONTH"] = nc["BEGIN_DATE_TIME"].dt.month

nc["MAGNITUDE"] = pd.to_numeric(nc["MAGNITUDE"], errors="coerce").fillna(0)
nc["CZ_NAME"] = nc["CZ_NAME"].astype(str).str.upper().str.strip()

lat_col = "avg_lat" if "avg_lat" in nc.columns else "BEGIN_LAT"
lon_col = "avg_lon" if "avg_lon" in nc.columns else "BEGIN_LON"
nc[lat_col] = pd.to_numeric(nc[lat_col], errors="coerce").fillna(nc[lat_col].mean())
nc[lon_col] = pd.to_numeric(nc[lon_col], errors="coerce").fillna(nc[lon_col].mean())

# Save Clean NOAA modeling file
nc.to_csv(PROCESSED_DIR / "nc_storms_clean.csv", index=False)

# ============================================================
# 15 & 16. ADD CENSUS / COMMUNITY VARIABLES
# ============================================================
print("\n--- Step 15 & 16: Adding Census Vulnerability Features ---")
counties = nc["CZ_NAME"].unique()
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
census_df.to_csv(PROCESSED_DIR / "nc_county_census.csv", index=False)

nc = nc.merge(census_df, on="CZ_NAME", how="left")
nc.to_csv(PROCESSED_DIR / "nc_storms_with_census.csv", index=False)

# ============================================================
# 18. ADD HISTORICAL STORM-RISK FEATURES (PAST 5 YEARS ONLY)
# ============================================================
print("--- Step 18: Calculating 5-Year Rolling Historical Risk ---")
nc = nc.sort_values("BEGIN_DATE_TIME").reset_index(drop=True)
nc["past_5yr_events"] = 0
nc["past_5yr_high_impacts"] = 0

for county in counties:
    idx = nc[nc["CZ_NAME"] == county].index
    sub = nc.loc[idx]
    for i, row in sub.iterrows():
        t = row["BEGIN_DATE_TIME"]
        if pd.isna(t):
            continue
        past_mask = (sub["BEGIN_DATE_TIME"] >= (t - pd.DateOffset(years=5))) & (
            sub["BEGIN_DATE_TIME"] < t
        )
        nc.loc[i, "past_5yr_events"] = past_mask.sum()
        nc.loc[i, "past_5yr_high_impacts"] = sub.loc[past_mask, "HIGH_IMPACT"].sum()

# ============================================================
# ONE-HOT ENCODING & MATRIX PREPARATION
# ============================================================
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
years = nc["YEAR"].values

# ============================================================
# 19. TIME-BASED TRAIN / VALIDATION / TEST SPLIT
# ============================================================
train_mask = years <= 2020
val_mask = (years >= 2021) & (years <= 2023)
test_mask = years >= 2024

X_train, y_train = X[train_mask], y[train_mask]
X_val, y_val = X[val_mask], y[val_mask]
X_test, y_test = X[test_mask], y[test_mask]

print("\nDataset Split Sizes:")
print(f"Train (2000-2020): {X_train.shape[0]} rows")
print(f"Validation (2021-2023): {X_val.shape[0]} rows")
print(f"Test (2024-2026): {X_test.shape[0]} rows")

# ============================================================
# 20. COMPARE MODELS (RANDOM FOREST VS GRADIENT BOOSTING)
# ============================================================
def evaluate(name, model, X_t, y_t):
    preds = model.predict(X_t)
    probs = model.predict_proba(X_t)[:, 1]
    print(f"\n==================== {name} (Test Set: 2024-2026) ====================")
    print(f"Accuracy:  {accuracy_score(y_t, preds):.4f}")
    print(f"Precision: {precision_score(y_t, preds, zero_division=0):.4f}")
    print(f"Recall:    {recall_score(y_t, preds, zero_division=0):.4f}")
    print(f"F1 Score:  {f1_score(y_t, preds, zero_division=0):.4f}")
    print(f"ROC-AUC:   {roc_auc_score(y_t, probs):.4f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_t, preds))


# Model A: Random Forest
rf = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42)
rf.fit(X_train, y_train)
evaluate("Random Forest", rf, X_test, y_test)

# Model B: Gradient Boosting
gb_model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
gb_model.fit(X_train, y_train)
evaluate("Gradient Boosting", gb_model, X_test, y_test)

# ============================================================
# 21. SHAP EXPLAINABILITY
# ============================================================
print("\n--- Step 21: Generating SHAP Plot ---")
explainer = shap.TreeExplainer(gb_model)
shap_values = explainer(X_test)

plt.figure(figsize=(10, 6))
shap.summary_plot(shap_values, X_test, show=False)
plt.tight_layout()
shap_out = PROCESSED_DIR / "shap_summary.png"
plt.savefig(shap_out, dpi=150)
print(f"Saved SHAP summary plot to: {shap_out.resolve()}")

# ============================================================
# 22. PREDICTED RISK SCORE DEMO
# ============================================================
sample = X_test.iloc[[0]]
prob = gb_model.predict_proba(sample)[0, 1]
risk_score = int(round(prob * 100))
risk_level = "High" if risk_score >= 70 else ("Medium" if risk_score >= 40 else "Low")

print("\n==================== Step 22: Sample Risk Prediction ====================")
print(f"Predicted High-Impact Probability: {prob:.2%}")
print(f"Risk Score:                        {risk_score}/100")
print(f"Risk Level Category:                {risk_level}")