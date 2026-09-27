import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# Setup
BASE_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "raw"

DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# Download the 26 complete calendar years from 2000 through 2025
START_YEAR = 2000
END_YEAR = 2026


def fetch_and_download():
    print("Fetching directory listing from NCEI server...")

    response = requests.get(BASE_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = [
        a["href"]
        for a in soup.find_all("a", href=True)
    ]

    # Match NOAA Storm Events details files
    pattern = re.compile(
        r"StormEvents_details-ftp_v1\.0_d(\d{4})_.*\.csv\.gz"
    )

    download_queue = []

    for link in links:
        match = pattern.search(link)

        if match:
            year = int(match.group(1))

            if START_YEAR <= year <= END_YEAR:
                download_queue.append(
                    (
                        link,
                        urljoin(BASE_URL, link)
                    )
                )

    # Sort files chronologically
    download_queue.sort(
        key=lambda item: item[0]
    )

    print(
        f"Found {len(download_queue)} matching files "
        f"for {START_YEAR}-{END_YEAR}.\n"
    )

    for idx, (filename, url) in enumerate(
        download_queue,
        1
    ):
        target_path = DOWNLOAD_DIR / filename

        # Skip files that already exist
        if target_path.exists():
            print(
                f"[{idx}/{len(download_queue)}] "
                f"Skipped (already exists): {filename}"
            )
            continue

        print(
            f"[{idx}/{len(download_queue)}] "
            f"Downloading: {filename}..."
        )

        res = requests.get(
            url,
            stream=True
        )
        res.raise_for_status()

        with open(target_path, "wb") as f:
            for chunk in res.iter_content(
                chunk_size=16384
            ):
                if chunk:
                    f.write(chunk)

    print(
        f"\nFinished! All files saved to:\n"
        f"{DOWNLOAD_DIR.resolve()}"
    )


if __name__ == "__main__":
    fetch_and_download()