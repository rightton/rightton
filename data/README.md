# Data files

Every data file lists where its values come from.

| File | Contents | Origin |
| --- | --- | --- |
| `materials.json` | R-values of layer materials for the assembly builder | Three DOE/NREL-published data files, see "Materials" below |
| `glazing.json` | Window glazing presets (U-factor, SHGC) | OpenStudio-HPXML `defaults.rb`, which cites LBNL Home Energy Saver |
| `input_ranges.json` | How far each kind of unmeasured input is moved (low and high) to work out the load range shown as "input confidence" | RightTon's own judgment, not a published source [CONFIRM]; each rule says what it covers. Review these before relying on the ranges. |
| `defaults.json` | Defaults RightTon applies to left-out inputs | Mostly OpenStudio-HPXML `defaults.rb`; each entry names its source |
| `ashrae622_wsf.csv` | Weather and shielding factor (WSF) by weather-station WMO number, used to turn a leakage area into annual-average natural air changes | Copied unchanged from OpenStudio-HPXML (`HPXMLtoOpenStudio/resources/data/ashrae622_wsf.csv`, commit fb18723), BSD-style license, see `core/NOTICE-OpenStudio-HPXML.md`. NREL attributes the values to ASHRAE Standard 62.2. |

| `weather_stations.json` | Design summaries (design temperatures, humidity, latitude, elevation, ground temperatures, weather and shielding factor) for 1,018 U.S. weather stations, keyed by WMO station number | Built by `tools/build_weather_stations.py` from the TMY3 EPW files of the **EnergyPlus weather data collection** published by the U.S. Department of Energy / NREL (<https://energyplus.net/weather>; index: `weather/master.geojson` in the EnergyPlus repository), fetched by `tools/download_tmy3_epw.py` on 2026-11-16. TMY3 is NREL's 1991-2005 typical meteorological year data set (Wilcox and Marion, *Users Manual for TMY3 Data Sets*, NREL/TP-581-43156, 2008). |

## Weather stations: what is and is not in the table

- **All 1,020 U.S. TMY3 files** in the collection were processed (50 states, DC, Puerto Rico, Guam, U.S. Virgin Islands). **1,018 are in the table.**
- **Two are excluded** because their hourly temperatures are physically impossible (hours above the 56.7 C world record): Hydaburg Seaplane, AK (WMO 703884) and Carroll, IA (WMO 725468). They are listed under `_excluded` in the file with the reason.
- **Design temperatures.** 865 stations use the ASHRAE design conditions printed in the EPW header (99 % heating and 1 % cooling drybulb, coincident wetbulb, daily range). The other 153 files have no such header; for those the values are derived from the file's 8,760 hourly values the same way the reference engine does (`rightton.weather.design_from_hourly`). Each entry's `design_source` says which. A typical-year file is a weaker basis for design temperatures than the long-term ASHRAE statistics, so treat those 153 as `estimated`.
- **TMYx is not included.** SPEC work item: "plus TMYx where TMY3 is missing". TMYx files are published at climate.onebuilding.org, which could not be reached from the build environment used (its network policy blocks that host). `tools/build_weather_stations.py` accepts any folder of EPW files, so TMYx stations can be added by running it on a folder that also holds them. [CONFIRM] which U.S. locations TMYx would add.

## Materials: where the R-values come from

`materials.json` names a source for every value. Three sources are used:

1. **OpenStudio-HPXML `materials.rb`** (NREL): gypsum board, wood, concrete, brick, stone, stucco, sidings, rigid foam, air space.
2. **EnergyPlus dataset `ASHRAE_2005_HOF_Materials.idf`** (U.S. DOE, in the EnergyPlus repository under `datasets/`), which reproduces ASHRAE Handbook of Fundamentals 2005, chapter 25, table 4: batts, loose-fill mineral fiber, EPS, wood shingles.
3. **NREL openstudio-standards `ashrae_90_1.materials.json`**, entries marked "From CEC Title24 2013" (the California Energy Commission's Title 24 materials list): plaster, spray foams, spray-applied cellulose, XPS, polyisocyanurate.

A test (`test_sourced_material_values`) repeats the unit conversion from each source figure.

**Two older values are still `estimated` and marked [CONFIRM]** (plus mineral wool board, below): loose-fill cellulose (R-3.5 per inch) and loose-fill vermiculite (R-2.2 per inch). Neither appears in the three data files above, and the documents that do publish them (DOE Energy Saver, ORNL, the ASHRAE Handbook itself) could not be opened from the build environment, whose network policy allows GitHub but not energy.gov, ornl.gov or similar hosts. The numbers are the commonly quoted ones, written from memory; the app flags them wherever they are used. Replace them when a citable source is at hand.

**Mineral wool board** (rigid stone wool, `mineral_wool_board`) is R-4.2 per inch, `estimated` and marked [CONFIRM]. None of the three data files above has a rigid mineral wool board (they list only batts and loose fill). Manufacturer data sheets for boards sold as exterior continuous insulation give R-4.2 to R-4.3 per inch (ASTM C518 at 75 F mean temperature), for example the Owens Corning Thermafiber RainBarrier data sheet (siplast.com, document siplast-thermafiber-rainbarrier-cpds-siplic018) and ROCKWOOL Comfortboard 80. Those figures were seen in a web search summary on 2026-11-18; the data sheets could not be opened from the build environment (manufacturer hosts are blocked there). The lower figure is used. To confirm: open one data sheet, check the R per inch and test conditions, update the source note and set confidence to `default`.

**Plaster on wood lath** has no published value for the combination in those files; it is the sum of its two layers (5/8 in gypsum plaster and 1/4 in wood lath), each from a cited value.

Rated products vary. Closed-cell spray foam and foil-faced polyisocyanurate are often rated higher than the generic values here; the builder lets the user enter the rated R-value of any layer.

Weather files (EPW) themselves are not stored here; the engine reads any EPW file the user supplies.
