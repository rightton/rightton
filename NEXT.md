# Next steps

State on 2026-11-18: SPEC.md build priorities 1 to 6 are built, and issues #1 to #9 have been worked
(see "Issues #1 to #9" below; #9 still needs repository settings). `python -m pytest core` (333 tests),
`python validation/compare.py` (129 snapshot houses, all pass, largest difference 0.00 %) and the browser
end-to-end test (`app/tests/e2e.cjs`, desktop and phone) pass locally. House file format is now 1.1.0
(`assemblies[].framing` and the `glazings` library); every 1.0 file still loads and calculates unchanged.

## Issues #1 to #9: what is left

- **#9 repository metadata is not set** (left open; "Refs #9"). An agent here cannot change repository
  settings. Someone with admin access: Settings > General > Description: "Free, open-source residential
  heating and cooling load calculator for real (and old) houses. An open-source alternative to Manual J
  load calculation software, for informational purposes only. Not affiliated with or approved by ACCA; Manual J® is a registered trademark
  of ACCA." Topics: `hvac`, `load-calculation`, `manual-j`, `building-science`, `energy-modeling`,
  `heat-pump`, `home-energy`. Whether naming a trademark this way is fine is a legal judgment, not checked.
- **Air spaces are R-1.0 at any thickness** (#3 leftover depth, empty cavities, furring and veneer gaps),
  as in the reference engine (OS-HPXML `Material.AirCavityClosed`, which says it assumes R-1.0 "for all air
  gap configurations since there is no correction for direction of heat flow"). [CONFIRM] Real values
  depend on gap width, heat-flow direction, mean temperature and surface emissivity: roughly flat for
  ordinary (non-foil) vertical gaps of about 3/4 in and up, lower for thin gaps, higher for heat flowing
  down, and much higher with a foil face. Possible improvement: a thickness/direction/emissivity table
  from a citable source, with a check against the reference first, since it uses the flat R-1.0.
- **#4 framing allowance**: derived from the reference engine's framing factors (walls 0.23 / 0.20,
  floors and ceilings 0.13 / 0.10, roofs 0.07); NREL does not cite where those come from, and the
  interpolation between 16 and 24 in and the single roof value are RightTon's choices [CONFIRM]. A share
  calculated from lumber is not varied in the input-confidence ranges (a typed `framing_frac` is).
- **#5**: brick thicknesses (8 and 12 in) are nominal; lime plaster uses the sand-aggregate plaster value
  [CONFIRM].
- **#8 "prints with the report"**: the section drawing is kept in print styles, but the printable report
  itself (priority 7) does not exist yet.
- **#10 ground-source loop sizing** is recorded in SPEC.md "Later"; not started, by design.

## To put the web app online (needs a repository admin; an agent on a feature branch cannot do it)

1. Merge this branch to `main`.
2. In the repository: Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. The `pages` workflow (`.github/workflows/pages.yml`) then builds `app/` and publishes it at
   <https://rightton.github.io/rightton/> on every push to `main`. The README already links there.
4. Check the first `pages` run. [CONFIRM] it has not been run yet, so the workflow itself is untested.

## Known gaps, most important first

### Things that affect answers

Done on 2026-11-16 (see the commits and `data/README.md`): the U.S. TMY3 weather-station table (1,018
stations), sourced material values (12 of 14), the roof interior air film by pitch, and input-confidence
load ranges in the core and the results view. What is left in this group:

- **TMYx stations are not in the weather table.** The work item asked for TMYx where TMY3 is missing;
  TMYx is published at climate.onebuilding.org, which the build environment could not reach. Run
  `tools/build_weather_stations.py` on a folder that also holds the TMYx EPW files. [CONFIRM] which
  locations that adds.
- **153 of the 1,018 stations have design temperatures derived from the typical-year hourly data**
  because their EPW file has no ASHRAE design-conditions header (each entry's `design_source` says so).
  Replace them with ASHRAE design values where an open source for those exists.
- **Two material values are still estimates**: loose-fill cellulose and vermiculite (`data/materials.json`,
  marked [CONFIRM]). No source for them could be reached (only GitHub was reachable; energy.gov, ornl.gov
  and similar are blocked there). Any citable open document that lists them will do.
- **The input-confidence ranges are RightTon's judgment** (`data/input_ranges.json`, marked [CONFIRM]):
  how far to move each kind of unmeasured input is not from a published source. Have someone with field
  experience review them. Compass directions are treated as known. Values taken from RightTon's lists
  (glazing presets, material R-values) and nine of the defaults are varied; other defaults (stories,
  duct area rules, vent areas, space heights) are not.
- **The combined range adds effects in quadrature**, as if inputs were independent. It is an indication,
  not a statistical interval, and inputs that move together (all wall areas from one tape measure) will be
  understated.
- **The layer builder is still validated by hand calculation only** (the reference takes finished
  R-values).
- **RightTon-only features have no reference to compare with**: porch as a space, windows facing a
  space, sealed attic as conditioned space, zone-to-zone transfer, equipment heat line, user infiltration
  shares, input-confidence ranges. All are hand-calculation tested; see validation/RESULTS.md.
- **Not ported from the reference**: ERV/HRV rated-efficiency conversion (effectiveness is entered
  directly; [CONFIRM] in `core/rightton/airflow.py`), ventilation through the air handler (CFIS), two
  heating or two cooling systems in one zone, systems serving part of a zone, evaporative coolers,
  tabulated default duct loads.
- **Supply registers and returns are recorded but not used**: room airflow (cfm per room) is not
  calculated yet (SPEC "Later"). The checker only warns about rooms with no register.

### Format and tools

- **HPXML export** (SPEC outputs) is not built; only HPXML import exists, in `validation/hpxml_reader.py`.
- **The LLM guide was tested once, with one model** (docs/LLM-GUIDE-TEST.md), and edited afterwards
  without a re-test. Repeat with other models and a harder house (two zones, basement, garage).
- **The app rewrites number spelling on save** (`8.0` becomes `8`); the data is the same. The Python
  tools round-trip JSON byte for byte.
- **Format converter for a future major version**: nothing needed until 2.0.

### Interface (priority 6 leftovers and priority 7)

- No printable report yet (priority 7); the page has basic print styles only.
- Assemblies added from a ready-made preset (masonry walls) are copies; there is no "update from preset".
- Scenario changes are edited as path/value rows. Friendlier pickers ("replace this assembly",
  "add storm windows to these openings") would help homeowners.
- The input-confidence card shows ranges for the baseline only, not for each scenario.
- No floor-plan or DXF import (priority 7). `outline_ft` is carried in the format but unused.
- Accessibility has had no audit beyond keyboard focus styles and labels. [CONFIRM] with a screen reader.
- The first load downloads about 15 MB (the Python runtime); it is cached afterwards. No offline
  (service worker) support yet.
- End-to-end test covers one desktop and one phone viewport in Chromium only. [CONFIRM] Safari and Firefox.

## Housekeeping

- CI (`.github/workflows/tests.yml`) runs the Python tests, the reference snapshot, the generated-docs
  check, example validation, and the app build plus browser test. It failed on GitHub for the first
  house-file commits because PyYAML was not installed there; fixed in the workflow.
- The reference engine (OpenStudio 3.11.0 + OpenStudio-HPXML fb18723) lives outside the repo; it is only
  needed to regenerate the snapshot (`validation/run_reference.sh`, `validation/stress/make_stress_cases.py`).
- After changing the schema or data files: `python tools/gen_format_docs.py`.
