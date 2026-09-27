import pandas as pd
from pathlib import Path
import re

RAW_DIR = Path("storm-risk-ai/data/raw")
PROCESSED_DIR = Path("storm-risk-ai/data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

POVERTY_PATH = RAW_DIR / "s1701.csv"
HOUSEHOLD_PATH = RAW_DIR / "s1101.csv"
OUTPUT_PATH = PROCESSED_DIR / "nc_county_census.csv"


def clean_label(value):
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def extract_county_name(column_name):
    match = re.match(r"(.+?) County, North Carolina!!", str(column_name))
    if not match:
        return None
    return match.group(1).strip().upper()


def find_row(df, search_terms):
    labels = df["Label (Grouping)"].astype(str).apply(clean_label)
    mask = pd.Series(True, index=df.index)

    for term in search_terms:
        mask &= labels.str.contains(
            term,
            case=False,
            na=False,
            regex=False
        )

    matches = df.loc[mask]
    if matches.empty:
        return None

    return matches.iloc[0]


def numeric(value):
    if pd.isna(value):
        return None

    value = str(value).replace(",", "").replace("%", "").strip()

    if value in ["", "-", "N", "(X)", "null", "None"]:
        return None

    try:
        return float(value)
    except ValueError:
        return None


print("--- Reading S1701 poverty data ---")

poverty = pd.read_csv(POVERTY_PATH, low_memory=False)

if "Label (Grouping)" not in poverty.columns:
    raise ValueError(
        "S1701 file does not contain 'Label (Grouping)'.\n"
        f"Columns found: {poverty.columns.tolist()}"
    )

poverty_row = find_row(
    poverty,
    ["Population for whom poverty status is determined"]
)

if poverty_row is None:
    print("\nCould not automatically find the overall poverty row.")
    print("Available row labels:")
    for label in poverty["Label (Grouping)"].dropna().unique():
        print("  ", clean_label(label))
    raise ValueError("Could not locate overall poverty row in S1701.")

poverty_results = []

for col in poverty.columns:
    county = extract_county_name(col)

    if county is None:
        continue

    if "Percent below poverty level!!Estimate" not in col:
        continue

    value = numeric(poverty_row[col])

    if value is not None:
        poverty_results.append(
            {
                "CZ_NAME": county,
                "poverty_rate": value / 100
            }
        )

poverty_clean = (
    pd.DataFrame(poverty_results)
    .drop_duplicates(subset="CZ_NAME")
)

print(f"Found poverty data for {len(poverty_clean)} counties.")


household_clean = None

if HOUSEHOLD_PATH.exists():
    print("\n--- Reading S1101 household data ---")

    households = pd.read_csv(
        HOUSEHOLD_PATH,
        low_memory=False
    )

    if "Label (Grouping)" not in households.columns:
        print(
            "Skipping S1101 because 'Label (Grouping)' was not found."
        )
    else:
        elderly_row = find_row(
            households,
            ["65 years"]
        )

        elderly_results = []

        if elderly_row is not None:
            for col in households.columns:
                county = extract_county_name(col)

                if county is None:
                    continue

                if "Percent" not in col or "Estimate" not in col:
                    continue

                value = numeric(elderly_row[col])

                if value is not None:
                    elderly_results.append(
                        {
                            "CZ_NAME": county,
                            "elderly_rate": value / 100
                        }
                    )

            household_clean = (
                pd.DataFrame(elderly_results)
                .drop_duplicates(subset="CZ_NAME")
            )

            print(
                f"Found elderly data for "
                f"{len(household_clean)} counties."
            )
        else:
            print(
                "Could not automatically find an age-65 row in S1101. "
                "Continuing with poverty data only."
            )


census = poverty_clean.copy()

if household_clean is not None and not household_clean.empty:
    census = census.merge(
        household_clean,
        on="CZ_NAME",
        how="left"
    )

census = census.sort_values("CZ_NAME").reset_index(drop=True)

census.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n--- Finished ---")
print(census.head(10))
print(f"\nNumber of counties: {len(census)}")
print(f"Columns: {census.columns.tolist()}")
print(f"Saved to: {OUTPUT_PATH.resolve()}")

if len(census) != 100:
    print(
        "\nWARNING: North Carolina has 100 counties, but this "
        f"file contains {len(census)}."
    )
    print(
        "Make sure you downloaded the Census table with "
        "'All counties within North Carolina' selected."
    )
