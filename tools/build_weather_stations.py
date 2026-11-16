#!/usr/bin/env python3
"""Build data/weather_stations.json from a folder of EPW weather files.

Usage: python tools/build_weather_stations.py <folder with .epw files>

Each station entry holds only the design summary the engine needs (see
rightton.weather.Weather), not the hourly data.
"""
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))
from rightton import weather  # noqa: E402

stations = {}
for epw in sorted(Path(sys.argv[1]).glob("*.epw")):
    wx = weather.read_epw(epw)
    entry = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dataclasses.asdict(wx).items()}
    entry["monthly_avg_drybulb_f"] = [round(v, 2) for v in wx.monthly_avg_drybulb_f]
    entry["shallow_ground_monthly_f"] = [round(v, 2) for v in wx.shallow_ground_monthly_f]
    entry["source_file"] = epw.name
    stations.setdefault(wx.wmo, entry)  # first file wins when two share a station number
out = {
    "_about": "Design summaries of weather stations, keyed by WMO station number. Built by "
              "tools/build_weather_stations.py from the EPW files distributed with OpenStudio-HPXML "
              "(weather/ folder, commit fb18723; TMY3 / TMYx / IWEC typical-year files). Starter set: "
              "any other station can be used by loading its EPW file in the app or by entering "
              "design_conditions in the house file.",
    "stations": stations,
}
(ROOT / "data" / "weather_stations.json").write_text(json.dumps(out, indent=1) + "\n")
print(len(stations), "stations")
