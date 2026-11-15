# Data files

Every data file lists where its values come from.

| File | Contents | Origin |
| --- | --- | --- |
| `ashrae622_wsf.csv` | Weather and shielding factor (WSF) by weather-station WMO number, used to turn a leakage area into annual-average natural air changes | Copied unchanged from OpenStudio-HPXML (`HPXMLtoOpenStudio/resources/data/ashrae622_wsf.csv`, commit fb18723), BSD-style license, see `core/NOTICE-OpenStudio-HPXML.md`. NREL attributes the values to ASHRAE Standard 62.2. |

Weather files (EPW) are not stored here; the engine reads any EPW file the user supplies.
