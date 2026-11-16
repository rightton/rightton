# Data files

Every data file lists where its values come from.

| File | Contents | Origin |
| --- | --- | --- |
| `ashrae622_wsf.csv` | Weather and shielding factor (WSF) by weather-station WMO number, used to turn a leakage area into annual-average natural air changes | Copied unchanged from OpenStudio-HPXML (`HPXMLtoOpenStudio/resources/data/ashrae622_wsf.csv`, commit fb18723), BSD-style license, see `core/NOTICE-OpenStudio-HPXML.md`. NREL attributes the values to ASHRAE Standard 62.2. |

| `weather_stations.json` | Design summaries (design temperatures, humidity, latitude, elevation, ground temperatures, weather and shielding factor) for 1,018 U.S. weather stations, keyed by WMO station number | Built by `tools/build_weather_stations.py` from the TMY3 EPW files of the **EnergyPlus weather data collection** published by the U.S. Department of Energy / NREL (<https://energyplus.net/weather>; index: `weather/master.geojson` in the EnergyPlus repository), fetched by `tools/download_tmy3_epw.py` on 2026-11-16. TMY3 is NREL's 1991-2005 typical meteorological year data set (Wilcox and Marion, *Users Manual for TMY3 Data Sets*, NREL/TP-581-43156, 2008). |

## Weather stations: what is and is not in the table

- **All 1,020 U.S. TMY3 files** in the collection were processed (50 states, DC, Puerto Rico, Guam, U.S. Virgin Islands). **1,018 are in the table.**
- **Two are excluded** because their hourly temperatures are physically impossible (hours above the 56.7 C world record): Hydaburg Seaplane, AK (WMO 703884) and Carroll, IA (WMO 725468). They are listed under `_excluded` in the file with the reason.
- **Design temperatures.** 865 stations use the ASHRAE design conditions printed in the EPW header (99 % heating and 1 % cooling drybulb, coincident wetbulb, daily range). The other 153 files have no such header; for those the values are derived from the file's 8,760 hourly values the same way the reference engine does (`rightton.weather.design_from_hourly`). Each entry's `design_source` says which. A typical-year file is a weaker basis for design temperatures than the long-term ASHRAE statistics, so treat those 153 as `estimated`.
- **TMYx is not included.** SPEC work item: "plus TMYx where TMY3 is missing". TMYx files are published at climate.onebuilding.org, which could not be reached from the build environment used (its network policy blocks that host). `tools/build_weather_stations.py` accepts any folder of EPW files, so TMYx stations can be added by running it on a folder that also holds them. [CONFIRM] which U.S. locations TMYx would add.

Weather files (EPW) themselves are not stored here; the engine reads any EPW file the user supplies.
