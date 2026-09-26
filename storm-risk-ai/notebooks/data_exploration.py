import pandas as pd
import glob

# Find all NOAA files by type
details_files = glob.glob("storm-risk-ai/data/raw/*details*.csv*")
location_files = glob.glob("storm-risk-ai/data/raw/*locations*.csv*")
fatality_files = glob.glob("storm-risk-ai/data/raw/*fatalities*.csv*")

print(len(details_files))
print(len(location_files))
print(len(fatality_files))

# Combine all yearly details files
details = pd.concat(
    [pd.read_csv(f, low_memory=False) for f in details_files],
    ignore_index=True
)

# Combine all yearly location files
locations = pd.concat(
    [pd.read_csv(f, low_memory=False) for f in location_files],
    ignore_index=True
)

# Combine all yearly fatality files
fatalities = pd.concat(
    [pd.read_csv(f, low_memory=False) for f in fatality_files],
    ignore_index=True
)

# Save the 3 combined datasets
#details.to_csv(
    #"storm-risk-ai/data/processed/details_2000_2025.csv",
    #index=False
#)

#locations.to_csv(
    #"storm-risk-ai/data/processed/locations_2000_2025.csv",
    #index=False
#)

#fatalities.to_csv(
    #"storm-risk-ai/data/processed/fatalities_2000_2025.csv",
    #index=False
#)

# Summarize locations so each EVENT_ID only has one row
location_summary = (
    locations.groupby("EVENT_ID")
    .agg(
        location_count=("EVENT_ID", "size"),
        avg_lat=("LATITUDE", "mean"),
        avg_lon=("LONGITUDE", "mean")
    )
    .reset_index()
)

# Summarize fatalities so each EVENT_ID only has one row
fatality_summary = (
    fatalities.groupby("EVENT_ID")
    .size()
    .reset_index(name="fatality_count")
)

# Merge location information into details
master = details.merge(
    location_summary,
    on="EVENT_ID",
    how="left"
)

# Merge fatality information into details
master = master.merge(
    fatality_summary,
    on="EVENT_ID",
    how="left"
)

# Events without location/fatality records get 0
master["location_count"] = master["location_count"].fillna(0)
master["fatality_count"] = master["fatality_count"].fillna(0)

# Save final ML dataset
#master.to_csv(
    #"storm-risk-ai/data/processed/storms_master_2000_2025.csv",
    #index=False
#)

# Check result
print("Details:", details.shape)
print("Locations:", locations.shape)
print("Fatalities:", fatalities.shape)
print("Master:", master.shape)

print(master.head())

nc = master[master["STATE"] == "NORTH CAROLINA"].copy()

event_types = [
    "Tornado",
    "Flash Flood",
    "Flood",
    "Thunderstorm Wind",
    "Hail"
]

nc = nc[nc["EVENT_TYPE"].isin(event_types)].copy()