"""
Exploration of NCEI Storm Events 2026 files (details, locations, fatalities).
Requires: pandas, matplotlib. Files can be local or downloaded from NCEI.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt

BASE = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
TAG = "d2026_c20260918"
FILES = {k: f"StormEvents_{k}-ftp_v1.0_{TAG}.csv.gz" for k in ["details", "locations", "fatalities"]}
OUT = "eda_output"
os.makedirs(OUT, exist_ok=True)


def load(name):
    path = FILES[name] if os.path.exists(FILES[name]) else BASE + FILES[name]
    return pd.read_csv(path, low_memory=False)


def parse_damage(s):
    """'10.00K' -> 10000.0, '1.5M' -> 1500000.0, 'B' = billions. NaN stays NaN."""
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}
    s = s.astype(str).str.strip().str.upper()
    num = pd.to_numeric(s.str.rstrip("KMB"), errors="coerce")
    factor = s.str[-1].map(mult).fillna(1)
    return num * factor


def overview(df, name):
    print(f"\n{'=' * 60}\n{name.upper()}  shape={df.shape}\n{'=' * 60}")
    print(df.dtypes.to_string())
    miss = (df.isna().mean() * 100).round(1).sort_values(ascending=False)
    print("\n% missing (top 15):\n", miss.head(15).to_string())
    print("\nNumeric summary:\n", df.describe().T.to_string())


# ---------- Load ----------
det = load("details")
loc = load("locations")
fat = load("fatalities")

# ---------- Clean details ----------
# Note: actual file uses 'DD-MON-YY HH:MM:SS' (e.g. 14-APR-26 19:00:00), not the PDF's MM/DD/YYYY
for c in ["BEGIN_DATE_TIME", "END_DATE_TIME"]:
    det[c] = pd.to_datetime(det[c], format="%d-%b-%y %H:%M:%S", errors="coerce")
det["DURATION_HR"] = (det.END_DATE_TIME - det.BEGIN_DATE_TIME).dt.total_seconds() / 3600
det["DMG_PROP_USD"] = parse_damage(det.DAMAGE_PROPERTY)
det["DMG_CROP_USD"] = parse_damage(det.DAMAGE_CROPS)
det["DMG_TOTAL_USD"] = det[["DMG_PROP_USD", "DMG_CROP_USD"]].sum(axis=1, min_count=1)
det["DEATHS_TOTAL"] = det.DEATHS_DIRECT + det.DEATHS_INDIRECT
det["INJURIES_TOTAL"] = det.INJURIES_DIRECT + det.INJURIES_INDIRECT
fat["FATALITY_DATE"] = pd.to_datetime(fat.FATALITY_DATE, format="%m/%d/%Y %H:%M:%S", errors="coerce")

for name, df in [("details", det), ("locations", loc), ("fatalities", fat)]:
    overview(df, name)

# ---------- Key integrity checks ----------
print("\n=== KEY CHECKS ===")
print("Duplicate EVENT_ID in details:", det.EVENT_ID.duplicated().sum())
print("Location rows w/o matching detail:", (~loc.EVENT_ID.isin(det.EVENT_ID)).sum())
print("Fatality rows w/o matching detail:", (~fat.EVENT_ID.isin(det.EVENT_ID)).sum())
print("Events with >=1 location row:", loc.EVENT_ID.nunique(), "of", len(det))
print("Max location rows per event:", loc.groupby("EVENT_ID").size().max())
print("Deaths in details:", int(det.DEATHS_TOTAL.sum()), "| fatality rows:", len(fat))
print("Date range:", det.BEGIN_DATE_TIME.min(), "to", det.BEGIN_DATE_TIME.max())

# ---------- Categorical breakdowns ----------
print("\n=== EVENT TYPES ===\n", det.EVENT_TYPE.value_counts().to_string())
print("\n=== TOP 15 STATES ===\n", det.STATE.value_counts().head(15).to_string())
print("\n=== EVENTS BY MONTH ===\n", det.groupby(det.BEGIN_DATE_TIME.dt.month).size().to_string())
print("\n=== TOR_F_SCALE ===\n", det.TOR_F_SCALE.value_counts().to_string())
print("\n=== FATALITY LOCATION ===\n", fat.FATALITY_LOCATION.value_counts().to_string())
print("\n=== FATALITY SEX ===\n", fat.FATALITY_SEX.value_counts(dropna=False).to_string())

impact = (det.groupby("EVENT_TYPE")
          .agg(events=("EVENT_ID", "size"), deaths=("DEATHS_TOTAL", "sum"),
               injuries=("INJURIES_TOTAL", "sum"), damage_usd=("DMG_TOTAL_USD", "sum"))
          .sort_values("damage_usd", ascending=False))
print("\n=== IMPACT BY EVENT TYPE ===\n", impact.to_string())
impact.to_csv(f"{OUT}/impact_by_event_type.csv")

print("\n=== TOP 10 COSTLIEST EVENTS ===")
print(det.nlargest(10, "DMG_TOTAL_USD")[["EVENT_ID", "STATE", "EVENT_TYPE", "BEGIN_DATE_TIME", "DMG_TOTAL_USD", "DEATHS_TOTAL"]].to_string(index=False))

# ---------- Recommended joins ----------
# 1) Aggregate fatalities to one row per event, then left-join (keeps 1 row per event)
fat_agg = (fat.groupby("EVENT_ID")
           .agg(fat_n=("FATALITY_ID", "size"),
                fat_direct=("FATALITY_TYPE", lambda x: (x == "D").sum()),
                fat_mean_age=("FATALITY_AGE", "mean"))
           .reset_index())
# 2) Aggregate locations to one row per event (point count + centroid)
loc_agg = (loc.groupby("EVENT_ID")
           .agg(loc_n=("LOCATION_INDEX", "size"),
                loc_lat_mean=("LATITUDE", "mean"), loc_lon_mean=("LONGITUDE", "mean"))
           .reset_index())
events = (det.merge(fat_agg, on="EVENT_ID", how="left", validate="1:1")
             .merge(loc_agg, on="EVENT_ID", how="left", validate="1:1"))
events[["fat_n", "fat_direct", "loc_n"]] = events[["fat_n", "fat_direct", "loc_n"]].fillna(0)
print("\nEvent-level table:", events.shape)
print("Mismatch DEATHS_TOTAL vs fatality rows:", (events.DEATHS_TOTAL != events.fat_n).sum())
events.to_csv(f"{OUT}/events_joined.csv.gz", index=False)

# 3) Person-level table: one row per fatality with event context (1:many is fine here)
fat_full = fat.merge(det[["EVENT_ID", "STATE", "EVENT_TYPE", "CZ_NAME", "BEGIN_LAT", "BEGIN_LON"]],
                     on="EVENT_ID", how="left", validate="m:1")
print("\nFatalities by event type:\n", fat_full.EVENT_TYPE.value_counts().to_string())

# ---------- Plots ----------
fig, ax = plt.subplots(2, 2, figsize=(14, 10))
det.EVENT_TYPE.value_counts().head(15).plot.barh(ax=ax[0, 0], title="Top 15 event types")
det.groupby(det.BEGIN_DATE_TIME.dt.month).size().plot.bar(ax=ax[0, 1], title="Events by month")
impact.damage_usd.head(10).div(1e6).plot.barh(ax=ax[1, 0], title="Damage by type ($M, top 10)")
fat.FATALITY_AGE.plot.hist(bins=20, ax=ax[1, 1], title="Fatality age distribution")
plt.tight_layout(); plt.savefig(f"{OUT}/overview.png", dpi=120)

fig, ax = plt.subplots(figsize=(12, 7))
pts = det.dropna(subset=["BEGIN_LAT", "BEGIN_LON"])
for t in pts.EVENT_TYPE.value_counts().head(6).index:
    s = pts[pts.EVENT_TYPE == t]
    ax.scatter(s.BEGIN_LON, s.BEGIN_LAT, s=3, alpha=0.4, label=t)
ax.set_xlim(-130, -65); ax.set_ylim(23, 50); ax.legend(markerscale=4)
ax.set_title("Event begin points (top 6 types, CONUS)")
plt.savefig(f"{OUT}/event_map.png", dpi=120)
print(f"\nOutputs written to ./{OUT}/")