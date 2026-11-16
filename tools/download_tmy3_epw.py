#!/usr/bin/env python3
"""Download every U.S. TMY3 EPW weather file in the EnergyPlus weather collection.

    python tools/download_tmy3_epw.py <folder to fill>

Source: the EnergyPlus weather data collection published by the U.S. Department of
Energy / NREL (https://energyplus.net/weather). The list of files is the index
`weather/master.geojson` in the EnergyPlus repository on GitHub; the files
themselves are on the collection's public storage (energyplus-weather.s3.amazonaws.com).
TMY3 is NREL's 1991-2005 typical meteorological year data set (Wilcox and Marion,
"Users Manual for TMY3 Data Sets", NREL/TP-581-43156, 2008).

About 1,020 files, 1.6 GB. Files already present are skipped.
"""
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

INDEX = "https://raw.githubusercontent.com/NREL/EnergyPlus/develop/weather/master.geojson"
US_PREFIXES = ("USA_", "PRI_", "GUM_", "VIR_")  # states and DC, Puerto Rico, Guam, U.S. Virgin Islands


def fetch(job):
    url, path = job
    if path.exists() and path.stat().st_size > 100_000:
        return None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                data = r.read()
            path.write_bytes(data)
            return None
        except Exception as e:  # noqa: BLE001 - retried, then reported
            error = e
    return f"{path.name}: {error}"


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "master.geojson"
    if not index_path.exists():
        urllib.request.urlretrieve(INDEX, index_path)
    jobs = []
    for feature in json.loads(index_path.read_text())["features"]:
        title = feature["properties"]["title"]
        if title.startswith(US_PREFIXES) and title.endswith("_TMY3"):
            url = re.search(r"href=(\S+?\.epw)>", feature["properties"]["epw"]).group(1)
            jobs.append((url, out / f"{title}.epw"))
    with ThreadPoolExecutor(16) as pool:
        failures = [f for f in pool.map(fetch, jobs) if f]
    print(f"{len(jobs)} TMY3 files listed, {len(failures)} failed")
    for f in failures:
        print("  ", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
