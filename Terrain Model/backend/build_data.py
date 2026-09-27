from __future__ import annotations

import json
import re
import shutil
import ssl
import sys
import urllib.request
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests


START_YEAR = 2000
END_YEAR = 2026
EXPECTED_YEARS = list(range(START_YEAR, END_YEAR + 1))

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FRONTEND_DATA_DIR = ROOT / "frontend" / "public" / "data"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)

COUNTY_GEOJSON = PROCESSED_DIR / "nc-counties.geojson"
STORM_JSON = PROCESSED_DIR / "storm-data.json"
TERRAIN_JSON = PROCESSED_DIR / "terrain.json"

STATE_FIPS = "37"

CENSUS_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2025/shp/"
    "cb_2025_us_county_500k.zip"
)

CENSUS_CACHE_DIR = PROCESSED_DIR / "census"
CENSUS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def print_header():
    print()
    print("NC Terrain Atlas data build")
    print(f"Years: {START_YEAR}–{END_YEAR}")
    print(f"Year count: {len(EXPECTED_YEARS)}")
    print()


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(column).strip().upper() for column in df.columns]
    return df


def find_year_file(prefix: str, year: int) -> Path | None:
    pattern = re.compile(
        rf"^{re.escape(prefix)}_v1\.0_d{year}_.*\.csv\.gz$",
        re.IGNORECASE,
    )

    matches = [
        path
        for path in RAW_DIR.iterdir()
        if path.is_file() and pattern.match(path.name)
    ]

    if not matches:
        return None

    matches.sort(key=lambda path: path.name)
    return matches[-1]


def find_all_year_files(prefix: str) -> dict[int, Path]:
    results: dict[int, Path] = {}

    for path in RAW_DIR.iterdir():
        if not path.is_file():
            continue

        match = re.match(
            rf"^{re.escape(prefix)}_v1\.0_d(\d{{4}})_.*\.csv\.gz$",
            path.name,
            re.IGNORECASE,
        )

        if not match:
            continue

        year = int(match.group(1))

        if START_YEAR <= year <= END_YEAR:
            existing = results.get(year)

            if existing is None or path.name > existing.name:
                results[year] = path

    return dict(sorted(results.items()))


def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def parse_damage(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)

    values = (
        series.astype(str)
        .str.strip()
        .str.upper()
        .replace(
            {
                "": "0",
                "NAN": "0",
                "NONE": "0",
                "NULL": "0",
                "0.00K": "0",
            }
        )
    )

    multipliers = np.ones(len(values), dtype=float)

    multipliers[
        values.str.endswith("K", na=False)
    ] = 1_000

    multipliers[
        values.str.endswith("M", na=False)
    ] = 1_000_000

    multipliers[
        values.str.endswith("B", na=False)
    ] = 1_000_000_000

    cleaned = (
        values.str.replace(r"[KMB]$", "", regex=True)
        .str.replace(",", "", regex=False)
    )

    numbers = pd.to_numeric(cleaned, errors="coerce").fillna(0)

    return numbers * multipliers


def make_geoid(state_fips: pd.Series, county_fips: pd.Series) -> pd.Series:
    state = (
        state_fips.astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
        .str.zfill(2)
    )

    county = (
        county_fips.astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
        .str.zfill(3)
    )

    return state + county


def load_noaa_details() -> pd.DataFrame:
    files = find_all_year_files("StormEvents_details-ftp")

    missing = [
        year
        for year in EXPECTED_YEARS
        if year not in files
    ]

    if missing:
        raise RuntimeError(
            "Missing NOAA details files for years: "
            + ", ".join(map(str, missing))
        )

    frames = []

    for year in EXPECTED_YEARS:
        path = files[year]

        print(f"Reading details {year}: {path.name}")

        df = pd.read_csv(
            path,
            compression="gzip",
            low_memory=False,
        )

        df = normalize_column_names(df)

        required = {
            "EVENT_ID",
            "STATE_FIPS",
            "CZ_FIPS",
            "CZ_TYPE",
        }

        missing_columns = required - set(df.columns)

        if missing_columns:
            raise RuntimeError(
                f"{path.name} is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        df = df[
            df["STATE_FIPS"].astype(str).str.zfill(2) == STATE_FIPS
        ]

        df = df[
            df["CZ_TYPE"].astype(str).str.upper() == "C"
        ]

        if df.empty:
            continue

        df["YEAR"] = year

        df["GEOID"] = make_geoid(
            df["STATE_FIPS"],
            df["CZ_FIPS"],
        )

        if "EVENT_TYPE" not in df.columns:
            df["EVENT_TYPE"] = "Unknown"

        df["EVENT_TYPE"] = (
            df["EVENT_TYPE"]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

        if "DAMAGE_PROPERTY" in df.columns:
            df["PROPERTY_DAMAGE"] = parse_damage(
                df["DAMAGE_PROPERTY"]
            )
        else:
            df["PROPERTY_DAMAGE"] = 0.0

        if "DAMAGE_CROPS" in df.columns:
            df["CROP_DAMAGE"] = parse_damage(
                df["DAMAGE_CROPS"]
            )
        else:
            df["CROP_DAMAGE"] = 0.0

        direct_injuries = (
            safe_numeric(df["INJURIES_DIRECT"])
            if "INJURIES_DIRECT" in df.columns
            else 0
        )

        indirect_injuries = (
            safe_numeric(df["INJURIES_INDIRECT"])
            if "INJURIES_INDIRECT" in df.columns
            else 0
        )

        direct_deaths = (
            safe_numeric(df["DEATHS_DIRECT"])
            if "DEATHS_DIRECT" in df.columns
            else 0
        )

        indirect_deaths = (
            safe_numeric(df["DEATHS_INDIRECT"])
            if "DEATHS_INDIRECT" in df.columns
            else 0
        )

        df["INJURIES_TOTAL"] = (
            direct_injuries + indirect_injuries
        )

        df["DEATHS_TOTAL"] = (
            direct_deaths + indirect_deaths
        )

        frames.append(
            df[
                [
                    "EVENT_ID",
                    "YEAR",
                    "GEOID",
                    "EVENT_TYPE",
                    "PROPERTY_DAMAGE",
                    "CROP_DAMAGE",
                    "INJURIES_TOTAL",
                    "DEATHS_TOTAL",
                ]
            ]
        )

    if not frames:
        raise RuntimeError(
            "No North Carolina county-level storm records were found."
        )

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    combined = combined.drop_duplicates(
        subset=["EVENT_ID"],
        keep="last",
    )

    print(
        f"Loaded {len(combined):,} "
        "North Carolina county-level storm records"
    )

    return combined


def load_location_data() -> pd.DataFrame:
    files = find_all_year_files("StormEvents_locations-ftp")

    if not files:
        print("No NOAA location files found")
        return pd.DataFrame(
            columns=[
                "EVENT_ID",
                "LOCATION_COUNT",
                "LATITUDE",
                "LONGITUDE",
            ]
        )

    frames = []

    for year, path in files.items():
        print(
            f"Reading locations {year}: {path.name}"
        )

        df = pd.read_csv(
            path,
            compression="gzip",
            low_memory=False,
        )

        df = normalize_column_names(df)

        if "EVENT_ID" not in df.columns:
            continue

        if "LATITUDE" not in df.columns:
            if "LAT" in df.columns:
                df["LATITUDE"] = df["LAT"]
            else:
                df["LATITUDE"] = np.nan

        if "LONGITUDE" not in df.columns:
            if "LON" in df.columns:
                df["LONGITUDE"] = df["LON"]
            elif "LONG" in df.columns:
                df["LONGITUDE"] = df["LONG"]
            else:
                df["LONGITUDE"] = np.nan

        df["LATITUDE"] = pd.to_numeric(
            df["LATITUDE"],
            errors="coerce",
        )

        df["LONGITUDE"] = pd.to_numeric(
            df["LONGITUDE"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["LATITUDE", "LONGITUDE"]
        )

        if df.empty:
            continue

        df["YEAR"] = year

        frames.append(
            df[
                [
                    "EVENT_ID",
                    "YEAR",
                    "LATITUDE",
                    "LONGITUDE",
                ]
            ]
        )

    if not frames:
        print("Loaded 0 event location summaries")

        return pd.DataFrame(
            columns=[
                "EVENT_ID",
                "LOCATION_COUNT",
                "LATITUDE",
                "LONGITUDE",
            ]
        )

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    grouped = (
        combined
        .groupby("EVENT_ID", as_index=False)
        .agg(
            LOCATION_COUNT=(
                "EVENT_ID",
                "count",
            ),
            LATITUDE=(
                "LATITUDE",
                "mean",
            ),
            LONGITUDE=(
                "LONGITUDE",
                "mean",
            ),
        )
    )

    print(
        f"Loaded {len(grouped):,} "
        "event location summaries"
    )

    return grouped


def load_fatality_data() -> pd.DataFrame:
    files = find_all_year_files("StormEvents_fatalities-ftp")

    if not files:
        print("No NOAA fatality files found")

        return pd.DataFrame(
            columns=[
                "EVENT_ID",
                "FATALITY_RECORDS",
            ]
        )

    frames = []

    for year, path in files.items():
        print(
            f"Reading fatalities {year}: {path.name}"
        )

        df = pd.read_csv(
            path,
            compression="gzip",
            low_memory=False,
        )

        df = normalize_column_names(df)

        if "EVENT_ID" not in df.columns:
            continue

        df["YEAR"] = year

        frames.append(
            df[
                [
                    "EVENT_ID",
                    "YEAR",
                ]
            ]
        )

    if not frames:
        print("Loaded 0 fatality-linked events")

        return pd.DataFrame(
            columns=[
                "EVENT_ID",
                "FATALITY_RECORDS",
            ]
        )

    combined = pd.concat(
        frames,
        ignore_index=True,
    )

    grouped = (
        combined
        .groupby("EVENT_ID", as_index=False)
        .size()
        .rename(
            columns={
                "size": "FATALITY_RECORDS"
            }
        )
    )

    print(
        f"Loaded {len(grouped):,} "
        "fatality-linked events"
    )

    return grouped


def build_yearly_profile(
    df: pd.DataFrame,
    years: list[int],
) -> dict:
    yearly = {}

    for year in years:
        year_df = df[df["YEAR"] == year]

        event_types = (
            year_df["EVENT_TYPE"]
            .value_counts()
            .to_dict()
        )

        yearly[str(year)] = {
            "events": int(len(year_df)),
            "propertyDamage": float(
                year_df["PROPERTY_DAMAGE"].sum()
            ),
            "cropDamage": float(
                year_df["CROP_DAMAGE"].sum()
            ),
            "injuries": float(
                year_df["INJURIES_TOTAL"].sum()
            ),
            "deaths": float(
                year_df["DEATHS_TOTAL"].sum()
            ),
            "eventTypes": {
                str(key): int(value)
                for key, value in event_types.items()
            },
        }

    return yearly


def average_yearly_profile(
    yearly: dict,
    years: list[int],
) -> dict:
    year_count = len(years)

    if year_count == 0:
        return {
            "events": 0,
            "propertyDamage": 0,
            "cropDamage": 0,
            "injuries": 0,
            "deaths": 0,
            "eventTypes": {},
        }

    totals = {
        "events": 0,
        "propertyDamage": 0,
        "cropDamage": 0,
        "injuries": 0,
        "deaths": 0,
    }

    event_type_totals = Counter()

    for year in years:
        profile = yearly.get(
            str(year),
            {
                "events": 0,
                "propertyDamage": 0,
                "cropDamage": 0,
                "injuries": 0,
                "deaths": 0,
                "eventTypes": {},
            },
        )

        totals["events"] += profile["events"]
        totals["propertyDamage"] += profile[
            "propertyDamage"
        ]
        totals["cropDamage"] += profile[
            "cropDamage"
        ]
        totals["injuries"] += profile[
            "injuries"
        ]
        totals["deaths"] += profile[
            "deaths"
        ]

        for event_type, count in profile[
            "eventTypes"
        ].items():
            event_type_totals[event_type] += count

    return {
        "events": totals["events"] / year_count,
        "propertyDamage": (
            totals["propertyDamage"] / year_count
        ),
        "cropDamage": (
            totals["cropDamage"] / year_count
        ),
        "injuries": (
            totals["injuries"] / year_count
        ),
        "deaths": (
            totals["deaths"] / year_count
        ),
        "eventTypes": {
            event_type: count / year_count
            for event_type, count in event_type_totals.most_common()
        },
    }


def build_storm_data(
    details: pd.DataFrame,
    locations: pd.DataFrame,
    fatalities: pd.DataFrame,
) -> dict:
    if not locations.empty:
        details = details.merge(
            locations,
            on="EVENT_ID",
            how="left",
        )
    else:
        details["LOCATION_COUNT"] = 0
        details["LATITUDE"] = np.nan
        details["LONGITUDE"] = np.nan

    if not fatalities.empty:
        details = details.merge(
            fatalities,
            on="EVENT_ID",
            how="left",
        )
    else:
        details["FATALITY_RECORDS"] = 0

    details["LOCATION_COUNT"] = (
        details["LOCATION_COUNT"]
        .fillna(0)
        .astype(int)
    )

    details["FATALITY_RECORDS"] = (
        details["FATALITY_RECORDS"]
        .fillna(0)
        .astype(int)
    )

    county_data = {}

    for geoid, county_df in details.groupby(
        "GEOID"
    ):
        yearly = build_yearly_profile(
            county_df,
            EXPECTED_YEARS,
        )

        overall_average = average_yearly_profile(
            yearly,
            EXPECTED_YEARS,
        )

        all_event_types = (
            county_df["EVENT_TYPE"]
            .value_counts()
            .to_dict()
        )

        county_data[str(geoid)] = {
            "geoid": str(geoid),
            "yearly": yearly,
            "overallAverage": overall_average,
            "eventTypes": {
                str(key): int(value)
                for key, value in all_event_types.items()
            },
            "locationEvents": int(
                county_df[
                    "LOCATION_COUNT"
                ].gt(0).sum()
            ),
            "fatalityLinkedEvents": int(
                county_df[
                    "FATALITY_RECORDS"
                ].gt(0).sum()
            ),
        }

    statewide_yearly = build_yearly_profile(
        details,
        EXPECTED_YEARS,
    )

    statewide_average = average_yearly_profile(
        statewide_yearly,
        EXPECTED_YEARS,
    )

    statewide_event_types = (
        details["EVENT_TYPE"]
        .value_counts()
        .to_dict()
    )

    return {
        "source": "NOAA Storm Events Database",
        "state": "North Carolina",
        "stateFips": STATE_FIPS,
        "startYear": START_YEAR,
        "endYear": END_YEAR,
        "yearCount": len(EXPECTED_YEARS),
        "years": EXPECTED_YEARS,
        "eventRecordCount": int(len(details)),
        "statewideYearly": statewide_yearly,
        "overallAverage": statewide_average,
        "statewideEventTypes": {
            str(key): int(value)
            for key, value in statewide_event_types.items()
        },
        "counties": county_data,
    }


def download_census_boundaries() -> Path:
    zip_path = CENSUS_CACHE_DIR / "counties.zip"

    if not zip_path.exists():
        print("Downloading Census county boundaries...")

        response = requests.get(
            CENSUS_URL,
            timeout=120,
            verify=False,
        )

        response.raise_for_status()

        zip_path.write_bytes(
            response.content
        )

        print("Census county boundary download complete")

    extract_dir = CENSUS_CACHE_DIR / "extracted"

    shp_files = list(
        extract_dir.glob("*.shp")
    )

    if shp_files:
        return shp_files[0]

    extract_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Extracting Census county boundaries...")

    with ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)

    shp_files = list(
        extract_dir.glob("*.shp")
    )

    if not shp_files:
        raise RuntimeError(
            "The Census county ZIP was downloaded, "
            "but no shapefile was found."
        )

    return shp_files[0]


def build_county_geojson(
    storm_data: dict,
) -> dict:
    print("Loading Census county boundaries...")

    shapefile = download_census_boundaries()

    counties = gpd.read_file(
        shapefile
    )

    counties = counties[
        counties["STATEFP"].astype(str).str.zfill(2)
        == STATE_FIPS
    ].copy()

    counties["GEOID"] = (
        counties["GEOID"]
        .astype(str)
        .str.zfill(5)
    )

    county_metrics = storm_data[
        "counties"
    ]

    counties["stormEvents"] = (
        counties["GEOID"]
        .map(
            lambda geoid: sum(
                storm_data[
                    "counties"
                ]
                .get(
                    geoid,
                    {}
                )
                .get(
                    "yearly",
                    {}
                )
                .get(
                    str(END_YEAR),
                    {}
                )
                .get(
                    "events",
                    0
                )
                for _ in [0]
            )
        )
    )

    features = []

    for _, row in counties.iterrows():
        geoid = str(row["GEOID"])

        county_profile = county_metrics.get(
            geoid,
            {},
        )

        yearly = county_profile.get(
            "yearly",
            {},
        )

        latest = yearly.get(
            str(END_YEAR),
            {
                "events": 0,
                "propertyDamage": 0,
                "cropDamage": 0,
                "injuries": 0,
                "deaths": 0,
                "eventTypes": {},
            },
        )

        average = county_profile.get(
            "overallAverage",
            {
                "events": 0,
                "propertyDamage": 0,
                "cropDamage": 0,
                "injuries": 0,
                "deaths": 0,
            },
        )

        geometry = row.geometry

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "GEOID": geoid,
                    "NAME": row.get(
                        "NAME",
                        geoid,
                    ),
                    "events": latest[
                        "events"
                    ],
                    "propertyDamage": latest[
                        "propertyDamage"
                    ],
                    "cropDamage": latest[
                        "cropDamage"
                    ],
                    "injuries": latest[
                        "injuries"
                    ],
                    "deaths": latest[
                        "deaths"
                    ],
                    "averageEvents": average[
                        "events"
                    ],
                    "averagePropertyDamage": average[
                        "propertyDamage"
                    ],
                    "averageCropDamage": average[
                        "cropDamage"
                    ],
                    "averageInjuries": average[
                        "injuries"
                    ],
                    "averageDeaths": average[
                        "deaths"
                    ],
                },
                "geometry": geometry.__geo_interface__,
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def fetch_terrain() -> dict:
    terrain_path = PROCESSED_DIR / "terrain.json"

    if terrain_path.exists():
        try:
            return json.loads(
                terrain_path.read_text()
            )
        except Exception:
            pass

    print("Building terrain metadata...")

    terrain = {
        "source": "USGS 3DEP",
        "state": "North Carolina",
        "bounds": {
            "west": -84.4,
            "south": 33.7,
            "east": -75.3,
            "north": 36.6,
        },
        "elevation": {
            "min": 0,
            "max": 6684,
            "unit": "feet",
        },
    }

    terrain_path.write_text(
        json.dumps(
            terrain,
            indent=2,
        )
    )

    return terrain


def write_json(
    path: Path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def publish_processed_data():
    files = [
        STORM_JSON,
        COUNTY_GEOJSON,
        TERRAIN_JSON,
    ]

    for source in files:
        if not source.exists():
            continue

        destination = (
            FRONTEND_DATA_DIR
            / source.name
        )

        shutil.copy2(
            source,
            destination,
        )

        print(
            f"Published {destination}"
        )


def main():
    print_header()

    details = load_noaa_details()

    locations = load_location_data()

    fatalities = load_fatality_data()

    storm_data = build_storm_data(
        details,
        locations,
        fatalities,
    )

    county_geojson = build_county_geojson(
        storm_data
    )

    terrain = fetch_terrain()

    write_json(
        STORM_JSON,
        storm_data,
    )

    write_json(
        COUNTY_GEOJSON,
        county_geojson,
    )

    write_json(
        TERRAIN_JSON,
        terrain,
    )

    publish_processed_data()

    print()
    print("Build complete.")
    print(
        f"Storm JSON:   {STORM_JSON}"
    )
    print(
        f"County GeoJSON: {COUNTY_GEOJSON}"
    )
    print(
        f"Terrain JSON:  {TERRAIN_JSON}"
    )
    print(
        f"Frontend data: {FRONTEND_DATA_DIR}"
    )
    print()


if __name__ == "__main__":
    main()