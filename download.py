import re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# Setup
BASE_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
DOWNLOAD_DIR = Path("CDSC 2026") / "Data_25_Years"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Select year range
START_YEAR = 2000
END_YEAR = 2026

def fetch_and_download():
    print("Fetching directory listing from NCEI server...")
    response = requests.get(BASE_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True)]

    # Matches details, locations, and fatalities files for target years
    pattern = re.compile(
        r"StormEvents_(details|locations|fatalities)-ftp_v1\.0_d(\d{4})_.*\.csv\.gz"
    )

    download_queue = []
    for link in links:
        match = pattern.search(link)
        if match:
            year = int(match.group(2))
            if START_YEAR <= year <= END_YEAR:
                download_queue.append((link, urljoin(BASE_URL, link)))

    print(f"Found {len(download_queue)} matching files to download.\n")

    for idx, (filename, url) in enumerate(download_queue, 1):
        target_path = DOWNLOAD_DIR / filename
        
        # Skip if already downloaded
        if target_path.exists():
            print(f"[{idx}/{len(download_queue)}] Skipped (already exists): {filename}")
            continue

        print(f"[{idx}/{len(download_queue)}] Downloading: {filename}...")
        res = requests.get(url, stream=True)
        res.raise_for_status()

        with open(target_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=16384):
                f.write(chunk)

    print(f"\nFinished! All files saved to: {DOWNLOAD_DIR.resolve()}")

if __name__ == "__main__":
    fetch_and_download()