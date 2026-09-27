from pathlib import Path
import pandas as pd

# ============================================================
# 1. Resolve paths relative to this script
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = SCRIPT_DIR.parent / "data" / "processed"

# Look for yearly csv files (e.g., storms_2000.csv, storms_2001.csv)
yearly_files = sorted(list(PROCESSED_DIR.glob("storms_*.csv")))

if not yearly_files:
    raise FileNotFoundError(
        f"No processed yearly storm CSVs found in: {PROCESSED_DIR.resolve()}\n"
        "Make sure your data processing step created 'storms_YYYY.csv' files in data/processed/."
    )

print(f"Found {len(yearly_files)} yearly files to process in {PROCESSED_DIR.name}.")

# ============================================================
# 2. Load and concatenate datasets
# ============================================================

dfs = [pd.read_csv(f, low_memory=False) for f in yearly_files]
master = pd.concat(dfs, ignore_index=True)

print("Master dataset shape:", master.shape)
print("\nColumns:")
print(master.columns.tolist())
print()

# ============================================================
# 3. Filter to North Carolina
# ============================================================

nc = master[master["STATE"] == "NORTH CAROLINA"].copy()

print("North Carolina dataset shape:", nc.shape)
print()

# ============================================================
# 4. Look at the storm types
# ============================================================

print("Storm types:")
print(nc["EVENT_TYPE"].value_counts().head(30))
print()

# ============================================================
# 5. Inspect property damage values
# ============================================================

print("Example property damage values:")
print(nc["DAMAGE_PROPERTY"].head(20))
print()

print("Most common property damage values:")
print(nc["DAMAGE_PROPERTY"].value_counts().head(30))
print()

# ============================================================
# 6. Convert property damage into numbers
# ============================================================

def convert_damage(value):
    if pd.isna(value):
        return 0.0

    value = str(value).strip().upper()

    if value == "" or value == "0":
        return 0.0

    if value.endswith("K"):
        return float(value[:-1]) * 1_000
    if value.endswith("M"):
        return float(value[:-1]) * 1_000_000
    if value.endswith("B"):
        return float(value[:-1]) * 1_000_000_000

    try:
        return float(value)
    except ValueError:
        return 0.0

nc["PROPERTY_DAMAGE_NUM"] = nc["DAMAGE_PROPERTY"].apply(convert_damage)

# ============================================================
# 7. Check that the conversion worked
# ============================================================

print("Original vs converted damage:")
print(nc[["DAMAGE_PROPERTY", "PROPERTY_DAMAGE_NUM"]].head(20))
print()

print("Property damage statistics:")
print(nc["PROPERTY_DAMAGE_NUM"].describe())
print()

# ============================================================
# 8. Look at the highest-damage events
# ============================================================

print("Highest property damage events:")
print(
    nc[["EVENT_ID", "EVENT_TYPE", "DAMAGE_PROPERTY", "PROPERTY_DAMAGE_NUM"]]
    .sort_values("PROPERTY_DAMAGE_NUM", ascending=False)
    .head(20)
)
print()

# ============================================================
# 9. Check for missing values
# ============================================================

print("Missing values:")
print(
    nc[["EVENT_ID", "EVENT_TYPE", "DAMAGE_PROPERTY", "PROPERTY_DAMAGE_NUM"]]
    .isna()
    .sum()
)
print()

# ============================================================
# 10. Save the cleaned North Carolina dataset
# ============================================================

output_file = PROCESSED_DIR / "nc_storms_clean.csv"
nc.to_csv(output_file, index=False)

print("Saved cleaned dataset successfully to:")
print(output_file.resolve())