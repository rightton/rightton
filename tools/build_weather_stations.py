#!/usr/bin/env python3
"""Build data/weather_stations.json from a folder of EPW weather files.

    python tools/download_tmy3_epw.py <folder>      # fetch the U.S. TMY3 files (1.6 GB)
    python tools/build_weather_stations.py <folder>

Each station entry holds only the design summary the engine needs (see
rightton.weather.Weather), not the hourly data. Design temperatures come from
the design-conditions header of each EPW file (ASHRAE climatic design data:
99 % heating and 1 % cooling drybulb with coincident wetbulb); where a file has
no usable header they are derived from its hourly data, and the entry says so.
"""
import csv
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
from rightton import weather  # noqa: E402

SOURCE = ("EnergyPlus weather data collection, U.S. Department of Energy / NREL (https://energyplus.net/weather; "
          "file index: weather/master.geojson in the EnergyPlus repository). TMY3 files: NREL typical "
          "meteorological year data, 1991-2005 (Wilcox and Marion, Users Manual for TMY3 Data Sets, "
          "NREL/TP-581-43156, 2008).")


def main():
    folder = Path(sys.argv[1])
    stations, skipped, duplicates, derived, excluded = {}, [], [], 0, {}
    for epw in sorted(folder.glob("*.epw")):
        try:
            wx = weather.read_epw(epw)
        except Exception as e:  # noqa: BLE001 - listed in the output, not hidden
            skipped.append(f"{epw.name}: {type(e).__name__}: {e}")
            continue
        with open(epw, newline="", encoding="latin-1") as f:
            rows = list(csv.reader(f))
        hourly_c = [float(r[6]) for r in rows[8:] if len(r) > 21]
        # Plausibility: no hour hotter than the world record (56.7 C) or colder than the U.S. record (-62 C)
        if max(hourly_c) > 56.7 or min(hourly_c) < -62.0:
            excluded[wx.wmo] = {"city": wx.city.title(), "state": rows[0][2], "source_file": epw.name,
                                "reason": f"hourly drybulb temperatures in the file run from {min(hourly_c):.1f} C to "
                                          f"{max(hourly_c):.1f} C, which is not physically plausible"}
            continue
        has_header = weather._design_from_header(rows[1]) is not None
        derived += not has_header
        entry = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dataclasses.asdict(wx).items()}
        entry["city"] = wx.city.title().replace(" Ap", " AP").replace("Afb", "AFB")
        entry["state"] = rows[0][2]
        entry["elevation_ft"] = round(wx.elevation_ft, 1)
        entry["heating_drybulb_f"] = round(wx.heating_drybulb_f, 2)
        entry["cooling_drybulb_f"] = round(wx.cooling_drybulb_f, 2)
        entry["daily_temp_range_f"] = round(wx.daily_temp_range_f, 2)
        entry["annual_avg_drybulb_f"] = round(wx.annual_avg_drybulb_f, 2)
        entry["monthly_avg_drybulb_f"] = [round(v, 1) for v in wx.monthly_avg_drybulb_f]
        entry["shallow_ground_monthly_f"] = [round(v, 1) for v in wx.shallow_ground_monthly_f]
        entry["design_source"] = "EPW design-conditions header" if has_header else "derived from the file's hourly data"
        entry["source_file"] = epw.name
        if wx.wmo in stations:
            duplicates.append(f"{epw.name} (kept {stations[wx.wmo]['source_file']})")
            continue
        stations[wx.wmo] = entry
    ordered = dict(sorted(stations.items(), key=lambda kv: (kv[1]["state"], kv[1]["city"])))
    out = {
        "_about": "Design summaries of U.S. weather stations, keyed by WMO station number. Built by "
                  "tools/build_weather_stations.py from EPW files fetched by tools/download_tmy3_epw.py. Any other "
                  "location can be used by loading its EPW file in the app or by entering design_conditions in "
                  "the house file.",
        "_source": SOURCE,
        "_excluded": excluded,
        "stations": ordered,
    }
    (ROOT / "data" / "weather_stations.json").write_text(json.dumps(out, separators=(",", ":")).replace('},"', '},\n"') + "\n")
    derived = sum(1 for e in ordered.values() if e["design_source"].startswith("derived"))
    print(f"{len(ordered)} stations written; {derived} with design conditions derived from hourly data; "
          f"{len(duplicates)} duplicate station numbers skipped; {len(skipped)} files could not be read")
    for wmo, e in excluded.items():
        print(f"   excluded {wmo} {e['city']}, {e['state']}: {e['reason']}")
    for line in duplicates + skipped:
        print("  ", line)


if __name__ == "__main__":
    main()
