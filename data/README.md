# Data files

Every data file lists where its values come from.

| File | Contents | Origin |
| --- | --- | --- |
| `materials.json` | R-values of layer materials for the assembly builder | Three DOE/NREL-published data files, see "Materials" below |
| `glazing.json` | Window glazing presets (U-factor, SHGC) | OpenStudio-HPXML `defaults.rb`, which cites LBNL Home Energy Saver |
| `input_ranges.json` | How far each kind of unmeasured input is moved (low and high) to work out the load range shown as "input confidence" | RightTon's own judgment, not a published source [CONFIRM]; each rule says what it covers. Review these before relying on the ranges. |
| `defaults.json` | Defaults RightTon applies to left-out inputs | Mostly OpenStudio-HPXML `defaults.rb`; each entry names its source |
| `ashrae622_wsf.csv` | Weather and shielding factor (WSF) by weather-station WMO number, used to turn a leakage area into annual-average natural air changes | Copied unchanged from OpenStudio-HPXML (`HPXMLtoOpenStudio/resources/data/ashrae622_wsf.csv`, commit fb18723), BSD-style license, see `core/NOTICE-OpenStudio-HPXML.md`. NREL attributes the values to ASHRAE Standard 62.2. |
| `assembly_presets.json` | Ready-made wall assemblies (solid brick of 2 and 3 wythes, plaster directly on brick, plaster on furring over brick, brick veneer over wood frame) that the app copies into a house file | Built only from materials in `materials.json` and framing in `framing.json`, each cited there. Thicknesses are typical: about 4 in per brick wythe (OpenStudio-HPXML uses 4.0 in for brick siding; the CEC Title 24 list has a 3 5/8 in fired-clay brick, plus mortar). Each preset's R-value is hand-checked in `core/tests/test_presets.py`. |
| `framing.json` | Actual sizes of nominal lumber, and the typical framing factors from which the allowance for plates, headers, corners and window framing is derived | OpenStudio-HPXML `materials.rb` (`Material.Stud2x`) and `constructions.rb` (`WoodStudConstructionSet` framing factors), commit fb18723, BSD-style license. See "Framing" below. |
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

**Sand-aggregate plaster** (`plaster_sand_aggregate`, for plaster troweled straight onto brick or stone) is R-0.199 per inch, from the CEC Title 24 entry "Plaster/Sand Aggregate - 1 in." (k = 5.0304 Btu-in/h-ft2-F) in NREL openstudio-standards. Historic lime plaster is not listed separately in those files; this is the closest sourced value [CONFIRM for lime plaster]. Its typical thickness (3/4 in) is a guess.

**Brick** uses OpenStudio-HPXML's brick conductivity (k = 5.5 Btu-in/h-ft2-F, R-0.182 per inch). The CEC Title 24 list gives a denser fired-clay brick at k = 8.22 (R-0.12 per inch); old soft brick varies, so treat solid-brick R-values as approximate either way.

**Plaster on wood lath** has no published value for the combination in those files; it is the sum of its two layers (5/8 in gypsum plaster and 1/4 in wood lath), each from a cited value.

Rated products vary. Closed-cell spray foam and foil-faced polyisocyanurate are often rated higher than the generic values here; the builder lets the user enter the rated R-value of any layer.

Weather files (EPW) themselves are not stored here; the engine reads any EPW file the user supplies.

## Framing: where the framing share comes from

Framing share = member share + allowance.

- **Member share** = actual member width / on-center spacing (1.5 / 16 = 0.094 for 2x4 at 16 in). Actual sizes
  come from OpenStudio-HPXML `materials.rb` `Material.Stud2x` (2x4 = 1.5 x 3.5 in, 2x6 = 1.5 x 5.5, 2x8 = 1.5 x 7.25,
  2x10 = 1.5 x 9.25, 2x12 = 1.5 x 11.25, 4x4 = 3.5 x 3.5). The lumber depth is also the cavity depth.
- **Allowance** for plates, headers, corners, blocking and window/door framing = the reference engine's typical
  framing factor minus the member share at the same spacing. The typical framing factors are the ones
  OpenStudio-HPXML `constructions.rb` uses to build wood-framed constructions: walls 0.23 (2x4 at 16 in) and 0.20
  (2x6 at 24 in), floors and ceilings 0.13 and 0.10, closed-cavity roofs 0.07 (24 in only). That gives allowances
  of 0.136 / 0.1375 for walls, 0.036 / 0.0375 for floors and ceilings and 0.0075 for roofs. NREL does not say
  where these framing factors come from; they match commonly used values but are not tied to a published
  survey here [CONFIRM].
- Between 16 and 24 in the allowance is interpolated, outside that range the nearest value is held, and the roof
  allowance is the same at every spacing. Those are RightTon's choices, not the source's [CONFIRM].
- The user can override the allowance (`framing.allowance_frac`) or the whole share (`framing_frac`).
